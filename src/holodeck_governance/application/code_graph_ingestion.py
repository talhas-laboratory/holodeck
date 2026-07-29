"""Governed factual code-graph ingestion and activation (M2-023).

Wires repository bindings, source observations, the extractor port, and
immutable SQLite persistence into one build/rebuild operation. Extractor output
is data only — it never grants instruction authority or raises readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from holodeck_governance.application.repository_extractor import (
    ExtractionRequest,
    ExtractionResult,
    RepositoryExtractor,
)
from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.domain.errors import (
    ContentionError,
    CrossTenantAccessError,
    IdempotencyConflictError,
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7, require_opaque_id
from holodeck_governance.domain.revisions import content_hash_for
from holodeck_governance.domain.workspace import RepositoryBinding, WorkspaceBindingStatus
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_COMMAND_CODE_GRAPH_BUILD,
    M2_EVENT_CODE_GRAPH_BUILD_COMPLETED,
    M2_EVENT_CODE_GRAPH_BUILD_FAILED,
    M2_EVENT_CODE_GRAPH_BUILD_PARTIAL,
    M2_EVENT_CODE_GRAPH_BUILD_REQUESTED,
    M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    ExtractionLimits,
    ExtractionRunStatus,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SnapshotStatus,
    assert_extraction_candidates_conform,
    assert_relation_endpoints_resolve,
    assert_snapshot_counts_match,
    code_graph_error,
    require_immutable_repository_revision,
)

M2_CODE_GRAPH_EVENT_SCHEMA_VERSION = "m2.workspace.code_graph.event.v1"
_RECEIPT_SNAPSHOT_PREFIX = "snapshot:"
_RECEIPT_RUN_PREFIX = "run:"
_RECEIPT_STATUS_PREFIX = "status:"
_PARTIAL_POLICY_NOTE = (
    "partial coverage requires explicit allow_partial_activation"
)


@dataclass(frozen=True, slots=True)
class GraphBuildRequest:
    """One idempotent graph build/rebuild against an immutable revision."""

    tenant_id: str
    workspace_object_id: str
    repository_binding_id: str
    repository_path: Path
    requested_revision: str
    actor_id: str
    idempotency_key: str
    limits: ExtractionLimits
    at: datetime
    base_snapshot_id: str | None = None
    path_includes: tuple[str, ...] = ()
    path_excludes: tuple[str, ...] = ()
    allow_partial_activation: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("workspace_object_id", self.workspace_object_id),
            ("repository_binding_id", self.repository_binding_id),
            ("actor_id", self.actor_id),
        ):
            require_opaque_id(value, name)
        if not self.idempotency_key.strip():
            raise MalformedCommandError("idempotency_key is required")
        require_immutable_repository_revision(self.requested_revision)
        if self.base_snapshot_id is not None:
            require_opaque_id(self.base_snapshot_id, "base_snapshot_id")
        if self.at.tzinfo is None:
            raise MalformedCommandError("at must be timezone-aware UTC")
        if not isinstance(self.repository_path, Path):
            raise MalformedCommandError("repository_path must be a Path")
        if self.limits.max_files is None and self.limits.max_entities is None:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT,
                "build requests require at least one of max_files or max_entities",
            )


@dataclass(frozen=True, slots=True)
class GraphBuildResult:
    """Outcome of one graph build, including durable event evidence."""

    snapshot_id: str
    extraction_run_id: str
    status: SnapshotStatus
    coverage_status: CoverageStatus
    entity_count: int
    relation_count: int
    actual_revision: str
    event_types: tuple[str, ...]
    replayed: bool
    coverage_notes: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphStatusView:
    """Read-only active snapshot and latest run status for one binding."""

    active_snapshot: RepositoryGraphSnapshot | None
    active_run: RepositoryExtractionRun | None


class CollaborationBindingPort(Protocol):
    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None: ...


class IntelligenceSourcePort(Protocol):
    def actor_has_permission(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        permission: str,
        at: datetime,
    ) -> bool: ...

    def require_workspace_object(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> None: ...

    def ensure_repository_file_source_observation(
        self,
        *,
        source_id: str,
        observation_id: str,
        tenant_id: str,
        workspace_object_id: str,
        locator: str,
        observed_revision: str,
        actor_id: str,
        at: datetime,
    ) -> None: ...


class CodeGraphStorePort(Protocol):
    def persist_building_graph(
        self,
        *,
        snapshot: RepositoryGraphSnapshot,
        run: RepositoryExtractionRun,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
    ) -> None: ...

    def activate_snapshot(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        activated_at: datetime,
        allow_partial_activation: bool = False,
    ) -> RepositoryGraphSnapshot: ...

    def claim_build_idempotency(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        semantic_hash: str,
        command_id: str,
        created_at: datetime,
    ) -> str: ...

    def release_build_idempotency_claim(
        self, *, tenant_id: str, idempotency_key: str
    ) -> None: ...

    def mark_snapshot_failed(
        self, snapshot_id: str, *, tenant_id: str, coverage_notes: tuple[str, ...]
    ) -> RepositoryGraphSnapshot: ...

    def get_snapshot(self, snapshot_id: str) -> RepositoryGraphSnapshot | None: ...

    def get_active_snapshot(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
    ) -> RepositoryGraphSnapshot | None: ...

    def get_extraction_run(
        self, extraction_run_id: str
    ) -> RepositoryExtractionRun | None: ...

    def list_snapshot_entities(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeEntityFact, ...]: ...


class DomainEventPort(Protocol):
    def append(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload: dict[str, object],
        correlation_id: str,
        causation_id: str,
        created_at: str,
        actor_id: str,
        payload_schema_version: str,
        occurred_at: str | None = None,
        subject_object_id: str | None = None,
    ) -> str: ...


class CommandReceiptPort(Protocol):
    def get_by_idempotency(
        self, tenant_id: str, idempotency_key: str
    ) -> tuple[str, CommandReceipt] | None: ...

    def save(
        self,
        receipt: CommandReceipt,
        *,
        idempotency_key: str,
        semantic_hash: str,
    ) -> None: ...


class CodeGraphIngestionService:
    """Application seam: extract → normalize → persist → activate | fail."""

    def __init__(
        self,
        *,
        collaboration: CollaborationBindingPort,
        intelligence: IntelligenceSourcePort,
        graphs: CodeGraphStorePort,
        extractor: RepositoryExtractor,
        events: DomainEventPort,
        receipts: CommandReceiptPort,
        commit,
    ) -> None:
        self._collaboration = collaboration
        self._intelligence = intelligence
        self._graphs = graphs
        self._extractor = extractor
        self._events = events
        self._receipts = receipts
        self._commit = commit

    def get_status(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
    ) -> GraphStatusView:
        require_opaque_id(tenant_id, "tenant_id")
        require_opaque_id(workspace_object_id, "workspace_object_id")
        require_opaque_id(repository_binding_id, "repository_binding_id")
        self._intelligence.require_workspace_object(
            workspace_object_id, tenant_id=tenant_id
        )
        binding = self._require_active_binding(
            repository_binding_id,
            tenant_id=tenant_id,
            workspace_object_id=workspace_object_id,
        )
        active = self._graphs.get_active_snapshot(
            tenant_id=tenant_id,
            workspace_object_id=workspace_object_id,
            repository_binding_id=binding.binding_id,
        )
        run = None
        if active is not None:
            run = self._graphs.get_extraction_run(active.extraction_run_id)
        return GraphStatusView(active_snapshot=active, active_run=run)

    def build_graph(self, request: GraphBuildRequest) -> GraphBuildResult:
        fingerprint = self._fingerprint(request)
        existing = self._receipts.get_by_idempotency(
            request.tenant_id, request.idempotency_key
        )
        if existing is not None:
            prior_hash, receipt = existing
            if prior_hash != fingerprint:
                raise IdempotencyConflictError(
                    "idempotency key was reused with different graph-build inputs"
                )
            return self._result_from_receipt(receipt, replayed=True)

        if not self._intelligence.actor_has_permission(
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            permission=INTELLIGENCE_CURATE_PERMISSION,
            at=request.at,
        ):
            raise MissingAuthorityError(
                "actor lacks workspace.intelligence.curate authority"
            )

        self._intelligence.require_workspace_object(
            request.workspace_object_id, tenant_id=request.tenant_id
        )
        binding = self._require_active_binding(
            request.repository_binding_id,
            tenant_id=request.tenant_id,
            workspace_object_id=request.workspace_object_id,
        )

        command_id = generate_uuidv7()
        claim = self._graphs.claim_build_idempotency(
            tenant_id=request.tenant_id,
            idempotency_key=request.idempotency_key,
            semantic_hash=fingerprint,
            command_id=command_id,
            created_at=request.at,
        )
        if claim == "already_complete":
            existing_after_claim = self._receipts.get_by_idempotency(
                request.tenant_id, request.idempotency_key
            )
            if existing_after_claim is None:
                raise MalformedCommandError(
                    "idempotency claim reported complete without a receipt"
                )
            _prior_hash, receipt = existing_after_claim
            return self._result_from_receipt(receipt, replayed=True)
        try:
            return self._build_graph_claimed(
                request=request,
                binding=binding,
                command_id=command_id,
                fingerprint=fingerprint,
            )
        finally:
            self._graphs.release_build_idempotency_claim(
                tenant_id=request.tenant_id,
                idempotency_key=request.idempotency_key,
            )

    def _build_graph_claimed(
        self,
        *,
        request: GraphBuildRequest,
        binding: RepositoryBinding,
        command_id: str,
        fingerprint: str,
    ) -> GraphBuildResult:
        snapshot_id = generate_uuidv7()
        extraction_run_id = generate_uuidv7()
        event_types: list[str] = []

        event_types.append(
            self._append_event(
                tenant_id=request.tenant_id,
                event_type=M2_EVENT_CODE_GRAPH_BUILD_REQUESTED,
                actor_id=request.actor_id,
                workspace_object_id=request.workspace_object_id,
                causation_id=command_id,
                at=request.at,
                payload={
                    "snapshot_id": snapshot_id,
                    "repository_binding_id": binding.binding_id,
                    "requested_revision": request.requested_revision,
                    "idempotency_key": request.idempotency_key,
                },
            )
        )

        try:
            extraction = self._extractor.extract(
                ExtractionRequest(
                    repository_path=request.repository_path,
                    tenant_id=request.tenant_id,
                    workspace_object_id=request.workspace_object_id,
                    repository_binding_id=binding.binding_id,
                    requested_revision=request.requested_revision,
                    limits=request.limits,
                    path_includes=request.path_includes,
                    path_excludes=request.path_excludes,
                    base_snapshot_id=request.base_snapshot_id,
                )
            )
        except Exception as exc:
            event_types.append(
                self._append_event(
                    tenant_id=request.tenant_id,
                    event_type=M2_EVENT_CODE_GRAPH_BUILD_FAILED,
                    actor_id=request.actor_id,
                    workspace_object_id=request.workspace_object_id,
                    causation_id=command_id,
                    at=request.at,
                    payload={
                        "snapshot_id": snapshot_id,
                        "reason": str(exc),
                        "phase": "extract",
                    },
                )
            )
            self._commit()
            result = GraphBuildResult(
                snapshot_id=snapshot_id,
                extraction_run_id=extraction_run_id,
                status=SnapshotStatus.FAILED,
                coverage_status=CoverageStatus.PARTIAL,
                entity_count=0,
                relation_count=0,
                actual_revision=request.requested_revision,
                event_types=tuple(event_types),
                replayed=False,
                coverage_notes=("extraction failed before persistence",),
                diagnostics=(str(exc),),
            )
            self._save_receipt(
                request=request,
                command_id=command_id,
                fingerprint=fingerprint,
                result=result,
                outcome="rejected",
                error_code=CodeGraphReason.MALFORMED_FACT.value,
            )
            return result

        return self._persist_and_activate(
            request=request,
            binding=binding,
            extraction=extraction,
            command_id=command_id,
            snapshot_id=snapshot_id,
            extraction_run_id=extraction_run_id,
            fingerprint=fingerprint,
            event_types=event_types,
        )

    def _persist_and_activate(
        self,
        *,
        request: GraphBuildRequest,
        binding: RepositoryBinding,
        extraction: ExtractionResult,
        command_id: str,
        snapshot_id: str,
        extraction_run_id: str,
        fingerprint: str,
        event_types: list[str],
    ) -> GraphBuildResult:
        if extraction.actual_revision != request.requested_revision:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "requested and actual revisions must match",
            )

        try:
            assert_extraction_candidates_conform(
                entities=extraction.candidate_entities,
                relations=extraction.candidate_relations,
                diagnostics=extraction.diagnostics,
            )
            assert_relation_endpoints_resolve(
                entities=extraction.candidate_entities,
                relations=extraction.candidate_relations,
            )
            self._ensure_sources_for_facts(
                request=request,
                entities=extraction.candidate_entities,
                relations=extraction.candidate_relations,
            )
        except Exception as exc:
            event_types.append(
                self._append_event(
                    tenant_id=request.tenant_id,
                    event_type=M2_EVENT_CODE_GRAPH_BUILD_FAILED,
                    actor_id=request.actor_id,
                    workspace_object_id=request.workspace_object_id,
                    causation_id=command_id,
                    at=request.at,
                    payload={
                        "snapshot_id": snapshot_id,
                        "reason": str(exc),
                        "phase": "normalize",
                    },
                )
            )
            self._commit()
            result = GraphBuildResult(
                snapshot_id=snapshot_id,
                extraction_run_id=extraction_run_id,
                status=SnapshotStatus.FAILED,
                coverage_status=CoverageStatus.PARTIAL,
                entity_count=0,
                relation_count=0,
                actual_revision=extraction.actual_revision,
                event_types=tuple(event_types),
                replayed=False,
                coverage_notes=("normalization/validation failed",),
                diagnostics=(str(exc),),
            )
            self._save_receipt(
                request=request,
                command_id=command_id,
                fingerprint=fingerprint,
                result=result,
                outcome="rejected",
                error_code=CodeGraphReason.MALFORMED_FACT.value,
            )
            return result

        entities = extraction.candidate_entities
        relations = extraction.candidate_relations
        coverage = extraction.coverage
        run_status = (
            ExtractionRunStatus.PARTIAL
            if coverage.status is CoverageStatus.PARTIAL
            else ExtractionRunStatus.SUCCEEDED
        )

        snapshot = RepositoryGraphSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=request.tenant_id,
            workspace_object_id=request.workspace_object_id,
            repository_binding_id=binding.binding_id,
            repository_revision=extraction.actual_revision,
            status=SnapshotStatus.BUILDING,
            extraction_run_id=extraction_run_id,
            coverage_status=coverage.status,
            entity_count=len(entities),
            relation_count=len(relations),
            created_by_actor_id=request.actor_id,
            created_at=request.at,
            base_snapshot_id=request.base_snapshot_id,
            coverage_notes=coverage.notes,
        )
        run = RepositoryExtractionRun(
            extraction_run_id=extraction_run_id,
            snapshot_id=snapshot_id,
            provider_key=extraction.provider.provider_key,
            provider_version=extraction.provider.provider_version,
            provider_schema_version=extraction.provider.provider_schema_version,
            configuration_hash=extraction.provider.configuration_hash,
            requested_revision=request.requested_revision,
            actual_revision=extraction.actual_revision,
            started_at=request.at,
            status=run_status,
            created_by_actor_id=request.actor_id,
            completed_at=request.at,
            diagnostics=extraction.diagnostics,
            limits=request.limits,
        )

        try:
            assert_snapshot_counts_match(
                snapshot, entities=entities, relations=relations
            )
            if (
                coverage.status is CoverageStatus.PARTIAL
                and not request.allow_partial_activation
            ):
                self._graphs.persist_building_graph(
                    snapshot=snapshot,
                    run=run,
                    entities=entities,
                    relations=relations,
                )
                policy_notes = coverage.notes + (_PARTIAL_POLICY_NOTE,)
                self._graphs.mark_snapshot_failed(
                    snapshot_id,
                    tenant_id=request.tenant_id,
                    coverage_notes=policy_notes,
                )
                event_types.append(
                    self._append_event(
                        tenant_id=request.tenant_id,
                        event_type=M2_EVENT_CODE_GRAPH_BUILD_PARTIAL,
                        actor_id=request.actor_id,
                        workspace_object_id=request.workspace_object_id,
                        causation_id=command_id,
                        at=request.at,
                        payload={
                            "snapshot_id": snapshot_id,
                            "extraction_run_id": extraction_run_id,
                            "entity_count": len(entities),
                            "relation_count": len(relations),
                            "coverage_status": coverage.status.value,
                        },
                    )
                )
                event_types.append(
                    self._append_event(
                        tenant_id=request.tenant_id,
                        event_type=M2_EVENT_CODE_GRAPH_BUILD_FAILED,
                        actor_id=request.actor_id,
                        workspace_object_id=request.workspace_object_id,
                        causation_id=command_id,
                        at=request.at,
                        payload={
                            "snapshot_id": snapshot_id,
                            "reason": _PARTIAL_POLICY_NOTE,
                            "phase": "partial_policy",
                        },
                    )
                )
                self._commit()
                result = GraphBuildResult(
                    snapshot_id=snapshot_id,
                    extraction_run_id=extraction_run_id,
                    status=SnapshotStatus.FAILED,
                    coverage_status=CoverageStatus.PARTIAL,
                    entity_count=len(entities),
                    relation_count=len(relations),
                    actual_revision=extraction.actual_revision,
                    event_types=tuple(event_types),
                    replayed=False,
                    coverage_notes=policy_notes,
                    diagnostics=tuple(d.code for d in extraction.diagnostics),
                )
                self._save_receipt(
                    request=request,
                    command_id=command_id,
                    fingerprint=fingerprint,
                    result=result,
                    outcome="rejected",
                    error_code=CodeGraphReason.PARTIAL_COVERAGE.value,
                )
                return result

            self._graphs.persist_building_graph(
                snapshot=snapshot,
                run=run,
                entities=entities,
                relations=relations,
            )
            activated = self._graphs.activate_snapshot(
                snapshot_id,
                tenant_id=request.tenant_id,
                activated_at=request.at,
                allow_partial_activation=request.allow_partial_activation,
            )
        except ContentionError:
            raise
        except Exception as exc:
            try:
                self._graphs.mark_snapshot_failed(
                    snapshot_id,
                    tenant_id=request.tenant_id,
                    coverage_notes=(f"activation/persist failed: {exc}",),
                )
            except Exception:
                pass
            event_types.append(
                self._append_event(
                    tenant_id=request.tenant_id,
                    event_type=M2_EVENT_CODE_GRAPH_BUILD_FAILED,
                    actor_id=request.actor_id,
                    workspace_object_id=request.workspace_object_id,
                    causation_id=command_id,
                    at=request.at,
                    payload={
                        "snapshot_id": snapshot_id,
                        "reason": str(exc),
                        "phase": "persist_or_activate",
                    },
                )
            )
            self._commit()
            result = GraphBuildResult(
                snapshot_id=snapshot_id,
                extraction_run_id=extraction_run_id,
                status=SnapshotStatus.FAILED,
                coverage_status=CoverageStatus.PARTIAL,
                entity_count=len(entities),
                relation_count=len(relations),
                actual_revision=extraction.actual_revision,
                event_types=tuple(event_types),
                replayed=False,
                coverage_notes=(f"activation/persist failed: {exc}",),
                diagnostics=tuple(d.code for d in extraction.diagnostics),
            )
            self._save_receipt(
                request=request,
                command_id=command_id,
                fingerprint=fingerprint,
                result=result,
                outcome="rejected",
                error_code=CodeGraphReason.MALFORMED_FACT.value,
            )
            return result

        completed_event = (
            M2_EVENT_CODE_GRAPH_BUILD_PARTIAL
            if coverage.status is CoverageStatus.PARTIAL
            else M2_EVENT_CODE_GRAPH_BUILD_COMPLETED
        )
        event_types.append(
            self._append_event(
                tenant_id=request.tenant_id,
                event_type=completed_event,
                actor_id=request.actor_id,
                workspace_object_id=request.workspace_object_id,
                causation_id=command_id,
                at=request.at,
                payload={
                    "snapshot_id": activated.snapshot_id,
                    "extraction_run_id": extraction_run_id,
                    "entity_count": activated.entity_count,
                    "relation_count": activated.relation_count,
                    "coverage_status": activated.coverage_status.value,
                },
            )
        )
        event_types.append(
            self._append_event(
                tenant_id=request.tenant_id,
                event_type=M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED,
                actor_id=request.actor_id,
                workspace_object_id=request.workspace_object_id,
                causation_id=command_id,
                at=request.at,
                payload={
                    "snapshot_id": activated.snapshot_id,
                    "repository_binding_id": binding.binding_id,
                    "repository_revision": activated.repository_revision,
                },
            )
        )
        self._commit()

        result = GraphBuildResult(
            snapshot_id=activated.snapshot_id,
            extraction_run_id=extraction_run_id,
            status=activated.status,
            coverage_status=activated.coverage_status,
            entity_count=activated.entity_count,
            relation_count=activated.relation_count,
            actual_revision=extraction.actual_revision,
            event_types=tuple(event_types),
            replayed=False,
            coverage_notes=activated.coverage_notes,
            diagnostics=tuple(d.code for d in extraction.diagnostics),
        )
        self._save_receipt(
            request=request,
            command_id=command_id,
            fingerprint=fingerprint,
            result=result,
            outcome="accepted",
            error_code=None,
        )
        return result

    def _ensure_sources_for_facts(
        self,
        *,
        request: GraphBuildRequest,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
    ) -> None:
        """Ensure file sources and observations so fact FKs resolve before insert."""

        seen: set[tuple[str, str, str]] = set()
        for entity in entities:
            key = (
                entity.repository_relative_path,
                entity.source_id,
                entity.source_observation_id,
            )
            if key in seen:
                continue
            seen.add(key)
            self._ensure_source(
                request=request,
                locator=entity.repository_relative_path,
                source_id=entity.source_id,
                observation_id=entity.source_observation_id,
            )
        for relation in relations:
            key = (
                f"evidence:{relation.evidence_source_id}",
                relation.evidence_source_id,
                relation.evidence_observation_id,
            )
            if key in seen:
                continue
            locator = next(
                (
                    e.repository_relative_path
                    for e in entities
                    if e.source_id == relation.evidence_source_id
                ),
                f"evidence/{relation.evidence_source_id}",
            )
            seen.add(key)
            self._ensure_source(
                request=request,
                locator=locator,
                source_id=relation.evidence_source_id,
                observation_id=relation.evidence_observation_id,
            )

    def _ensure_source(
        self,
        *,
        request: GraphBuildRequest,
        locator: str,
        source_id: str,
        observation_id: str,
    ) -> None:
        self._intelligence.ensure_repository_file_source_observation(
            source_id=source_id,
            observation_id=observation_id,
            tenant_id=request.tenant_id,
            workspace_object_id=request.workspace_object_id,
            locator=locator,
            observed_revision=request.requested_revision,
            actor_id=request.actor_id,
            at=request.at,
        )

    def _require_active_binding(
        self,
        binding_id: str,
        *,
        tenant_id: str,
        workspace_object_id: str,
    ) -> RepositoryBinding:
        binding = self._collaboration.get_repository_binding(binding_id)
        if binding is None:
            raise NotFoundGovernanceError("repository binding not found")
        if binding.tenant_id != tenant_id:
            raise CrossTenantAccessError("repository binding tenant mismatch")
        if binding.workspace_object_id != workspace_object_id:
            raise MalformedCommandError(
                "repository binding does not belong to workspace"
            )
        if binding.status is not WorkspaceBindingStatus.ACTIVE:
            raise MalformedCommandError(
                "repository binding must be active for graph ingestion"
            )
        return binding

    def _fingerprint(self, request: GraphBuildRequest) -> str:
        caps = self._extractor.describe_capabilities()
        return content_hash_for(
            {
                "command_type": M2_COMMAND_CODE_GRAPH_BUILD,
                "tenant_id": request.tenant_id,
                "workspace_object_id": request.workspace_object_id,
                "repository_binding_id": request.repository_binding_id,
                "requested_revision": request.requested_revision,
                "provider_key": caps.provider.provider_key,
                "provider_version": caps.provider.provider_version,
                "provider_schema_version": caps.provider.provider_schema_version,
                "configuration_hash": caps.provider.configuration_hash,
                "base_snapshot_id": request.base_snapshot_id,
                "path_includes": list(request.path_includes),
                "path_excludes": list(request.path_excludes),
                "limits": {
                    "max_files": request.limits.max_files,
                    "max_file_bytes": request.limits.max_file_bytes,
                    "max_entities": request.limits.max_entities,
                    "max_relations": request.limits.max_relations,
                    "max_seconds": request.limits.max_seconds,
                },
                "allow_partial_activation": request.allow_partial_activation,
            }
        )

    def _save_receipt(
        self,
        *,
        request: GraphBuildRequest,
        command_id: str,
        fingerprint: str,
        result: GraphBuildResult,
        outcome: str,
        error_code: str | None,
    ) -> None:
        receipt = CommandReceipt(
            receipt_id=generate_uuidv7(),
            command_id=command_id,
            tenant_id=request.tenant_id,
            outcome=outcome,
            reason_codes=(
                f"{_RECEIPT_SNAPSHOT_PREFIX}{result.snapshot_id}",
                f"{_RECEIPT_RUN_PREFIX}{result.extraction_run_id}",
                f"{_RECEIPT_STATUS_PREFIX}{result.status.value}",
            ),
            error_code=error_code,
            created_at=request.at,
        )
        self._receipts.save(
            receipt,
            idempotency_key=request.idempotency_key,
            semantic_hash=fingerprint,
        )
        self._commit()

    def _result_from_receipt(
        self, receipt: CommandReceipt, *, replayed: bool
    ) -> GraphBuildResult:
        snapshot_id = None
        run_id = None
        status = SnapshotStatus.FAILED
        for code in receipt.reason_codes:
            if code.startswith(_RECEIPT_SNAPSHOT_PREFIX):
                snapshot_id = code.removeprefix(_RECEIPT_SNAPSHOT_PREFIX)
            elif code.startswith(_RECEIPT_RUN_PREFIX):
                run_id = code.removeprefix(_RECEIPT_RUN_PREFIX)
            elif code.startswith(_RECEIPT_STATUS_PREFIX):
                status = SnapshotStatus(code.removeprefix(_RECEIPT_STATUS_PREFIX))
        if snapshot_id is None or run_id is None:
            raise MalformedCommandError("graph-build receipt missing snapshot identity")
        snapshot = self._graphs.get_snapshot(snapshot_id)
        if snapshot is None:
            return GraphBuildResult(
                snapshot_id=snapshot_id,
                extraction_run_id=run_id,
                status=status,
                coverage_status=CoverageStatus.PARTIAL,
                entity_count=0,
                relation_count=0,
                actual_revision="",
                event_types=(),
                replayed=replayed,
                coverage_notes=("replay of failed build with no persisted snapshot",),
            )
        return GraphBuildResult(
            snapshot_id=snapshot.snapshot_id,
            extraction_run_id=snapshot.extraction_run_id,
            status=snapshot.status,
            coverage_status=snapshot.coverage_status,
            entity_count=snapshot.entity_count,
            relation_count=snapshot.relation_count,
            actual_revision=snapshot.repository_revision,
            event_types=(),
            replayed=replayed,
            coverage_notes=snapshot.coverage_notes,
        )

    def _append_event(
        self,
        *,
        tenant_id: str,
        event_type: str,
        actor_id: str,
        workspace_object_id: str,
        causation_id: str,
        at: datetime,
        payload: dict[str, object],
    ) -> str:
        self._events.append(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            correlation_id=workspace_object_id,
            causation_id=causation_id,
            created_at=at.isoformat(),
            actor_id=actor_id,
            payload_schema_version=M2_CODE_GRAPH_EVENT_SCHEMA_VERSION,
            occurred_at=at.isoformat(),
            subject_object_id=workspace_object_id,
        )
        return event_type
