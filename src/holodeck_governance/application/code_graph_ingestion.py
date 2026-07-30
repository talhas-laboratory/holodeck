"""Governed factual code-graph ingestion and activation (M2-023).

Wires repository bindings, source observations, the extractor port, and
immutable SQLite persistence into one build/rebuild operation. Extractor output
is data only — it never grants instruction authority or raises readiness.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Protocol

from holodeck_governance.application.repository_extractor import (
    ExtractionCoverage,
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
from holodeck_governance.domain.workspace import (
    RepositoryBinding,
    WorkspaceBindingStatus,
)
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
    FactualGraphReadiness,
    IncrementalMergeStats,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SnapshotStatus,
    assert_extraction_candidates_conform,
    assert_relation_endpoints_resolve,
    assert_snapshot_counts_match,
    code_graph_error,
    deleted_paths_after_refresh,
    evaluate_factual_graph_readiness,
    merge_incremental_facts,
    plan_incremental_refresh,
    require_immutable_repository_revision,
)

_TRUNCATION_DIAGNOSTIC_CODES = frozenset(
    {
        "file_limit",
        "entity_limit",
        "relation_limit",
        "time_limit",
        "file_too_large",
    }
)

M2_CODE_GRAPH_EVENT_SCHEMA_VERSION = "m2.workspace.code_graph.event.v1"
_RECEIPT_SNAPSHOT_PREFIX = "snapshot:"
_RECEIPT_RUN_PREFIX = "run:"
_RECEIPT_STATUS_PREFIX = "status:"
_PARTIAL_POLICY_NOTE = (
    "partial coverage cannot activate until a durable policy-decision seam exists"
)
_BASE_SNAPSHOT_NOT_CURRENT = "base_snapshot_not_current"


def _build_claim_lease_seconds(limits: ExtractionLimits) -> int:
    """Bound an in-progress idempotency claim without leaving crash deadlocks.

    Extraction limits are deliberately explicit.  A caller-provided time limit
    receives five minutes of persistence/activation allowance; builds without
    one use the conservative fifteen-minute default until M2 adds a renewable
    worker lease.
    """

    if limits.max_seconds is None:
        return 15 * 60
    return max(60, limits.max_seconds + 5 * 60)


@dataclass(frozen=True, slots=True)
class GraphBuildRequest:
    """One idempotent graph build/rebuild against an immutable revision.

    ``base_snapshot_id`` is only for incremental reuse/lineage. Activation CAS
    uses ``expected_active_snapshot_id`` or ``expect_no_active_snapshot`` —
    ``None`` never means “skip comparison.”
    """

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
    expected_active_snapshot_id: str | None = None
    expect_no_active_snapshot: bool = False
    path_includes: tuple[str, ...] = ()
    path_excludes: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()

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
        if self.expected_active_snapshot_id is not None:
            require_opaque_id(
                self.expected_active_snapshot_id, "expected_active_snapshot_id"
            )
        if (
            self.expect_no_active_snapshot
            and self.expected_active_snapshot_id is not None
        ):
            raise MalformedCommandError(
                "expect_no_active_snapshot cannot be combined with "
                "expected_active_snapshot_id"
            )
        if (
            not self.expect_no_active_snapshot
            and self.expected_active_snapshot_id is None
        ):
            raise MalformedCommandError(
                "graph builds require expected_active_snapshot_id or "
                "expect_no_active_snapshot=True"
            )
        if self.changed_paths and self.base_snapshot_id is None:
            raise MalformedCommandError("changed_paths require base_snapshot_id")
        if self.at.tzinfo is None:
            raise MalformedCommandError("at must be timezone-aware UTC")
        if not isinstance(self.repository_path, Path):
            raise MalformedCommandError("repository_path must be a Path")
        if self.limits.max_files is None and self.limits.max_entities is None:
            raise code_graph_error(
                CodeGraphReason.QUERY_LIMIT,
                "build requests require at least one of max_files or max_entities",
            )
        for name, values in (
            ("path_includes", self.path_includes),
            ("path_excludes", self.path_excludes),
            ("changed_paths", self.changed_paths),
        ):
            for item in values:
                if not item.strip():
                    raise code_graph_error(
                        CodeGraphReason.MALFORMED_FACT,
                        f"{name} entries must be non-empty",
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
    reused_entity_count: int = 0
    rebuilt_entity_count: int = 0
    reused_relation_count: int = 0
    rebuilt_relation_count: int = 0
    incremental: bool = False
    fallback_full: bool = False


@dataclass(frozen=True, slots=True)
class GraphStatusView:
    """Read-only active snapshot and latest run status for one binding."""

    active_snapshot: RepositoryGraphSnapshot | None
    active_run: RepositoryExtractionRun | None
    factual_graph_readiness: FactualGraphReadiness = FactualGraphReadiness.ABSENT
    observed_repository_revision: str | None = None


class CollaborationBindingPort(Protocol):
    def get_repository_binding(self, binding_id: str) -> RepositoryBinding | None: ...


class RepositoryHeadObservationPort(Protocol):
    """Optional adapter/store of the authoritative observed repository head."""

    def observe_repository_head(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
    ) -> str | None: ...


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

    def stage_repository_file_source_observation(
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

    def activate_source_observation_pointer(
        self,
        *,
        source_id: str,
        observation_id: str,
        observed_revision: str,
        actor_id: str,
        at: datetime,
    ) -> None: ...

    def get_source_by_locator(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        locator: str,
    ) -> object | None: ...

    def record_repository_file_removed(
        self,
        source_id: str,
        *,
        observed_revision: str,
        actor_id: str,
        at: datetime,
    ) -> object: ...

    @contextmanager
    def participate_in_external_transaction(self) -> Iterator[None]: ...


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
        expected_active_snapshot_id: str | None = None,
        expect_no_active_snapshot: bool = False,
    ) -> RepositoryGraphSnapshot: ...

    def run_activation_unit_of_work(
        self,
        *,
        snapshot_id: str,
        tenant_id: str,
        activated_at: datetime,
        expected_active_snapshot_id: str | None,
        expect_no_active_snapshot: bool,
        steps: tuple[tuple[str, Callable[[], None]], ...],
        fault_before: str | None = None,
    ) -> RepositoryGraphSnapshot: ...

    def claim_build_idempotency(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        semantic_hash: str,
        command_id: str,
        created_at: datetime,
        lease_seconds: int,
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

    def list_snapshot_relations(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeRelationFact, ...]: ...

    def require_snapshot(
        self, snapshot_id: str, *, tenant_id: str
    ) -> RepositoryGraphSnapshot: ...


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
        repository_head: RepositoryHeadObservationPort | None = None,
        activation_fault_before: str | None = None,
    ) -> None:
        self._collaboration = collaboration
        self._intelligence = intelligence
        self._graphs = graphs
        self._extractor = extractor
        self._events = events
        self._receipts = receipts
        self._commit = commit
        self._repository_head = repository_head
        self._activation_fault_before = activation_fault_before

    def get_status(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
        observed_repository_revision: str | None = None,
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
        head = observed_repository_revision
        if head is None and self._repository_head is not None:
            head = self._repository_head.observe_repository_head(
                tenant_id=tenant_id,
                workspace_object_id=workspace_object_id,
                repository_binding_id=binding.binding_id,
            )
        readiness = evaluate_factual_graph_readiness(
            active_snapshot=active,
            active_run=run,
            binding_repository_revision=head,
        )
        return GraphStatusView(
            active_snapshot=active,
            active_run=run,
            factual_graph_readiness=readiness,
            observed_repository_revision=head,
        )

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
            lease_seconds=_build_claim_lease_seconds(request.limits),
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

        incremental = False
        fallback_full = False
        merge_stats = IncrementalMergeStats(
            reused_entities=0,
            rebuilt_entities=0,
            reused_relations=0,
            rebuilt_relations=0,
        )

        try:
            extraction, incremental, fallback_full, merge_stats, deleted_paths = (
                self._extract_for_build(
                    request=request,
                    binding=binding,
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
                incremental=incremental,
                fallback_full=fallback_full,
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
            merge_stats=merge_stats,
            incremental=incremental,
            fallback_full=fallback_full,
            deleted_paths=deleted_paths,
        )

    def _extract_for_build(
        self,
        *,
        request: GraphBuildRequest,
        binding: RepositoryBinding,
    ) -> tuple[
        ExtractionResult,
        bool,
        bool,
        IncrementalMergeStats,
        tuple[str, ...],
    ]:
        """Extract facts, optionally merging an incremental neighborhood.

        Returns ``(extraction, incremental, fallback_full, merge_stats, deleted_paths)``.
        """

        empty_stats = IncrementalMergeStats(
            reused_entities=0,
            rebuilt_entities=0,
            reused_relations=0,
            rebuilt_relations=0,
        )

        if request.base_snapshot_id is not None and request.changed_paths:
            base = self._graphs.require_snapshot(
                request.base_snapshot_id, tenant_id=request.tenant_id
            )
            if base.workspace_object_id != request.workspace_object_id:
                raise MalformedCommandError(
                    "base snapshot does not belong to workspace"
                )
            if base.repository_binding_id != binding.binding_id:
                raise MalformedCommandError(
                    "base snapshot does not belong to repository binding"
                )
            base_entities = self._graphs.list_snapshot_entities(
                base.snapshot_id, tenant_id=request.tenant_id
            )
            base_relations = self._graphs.list_snapshot_relations(
                base.snapshot_id, tenant_id=request.tenant_id
            )
            plan = plan_incremental_refresh(
                changed_paths=request.changed_paths,
                base_entities=base_entities,
                base_relations=base_relations,
            )
            if not plan.fallback_full:
                path_includes = tuple(
                    sorted(set(request.path_includes) | set(plan.reextract_paths))
                )
                neighborhood = self._extractor.extract(
                    self._extraction_request(
                        request,
                        binding=binding,
                        path_includes=path_includes,
                        changed_paths=request.changed_paths,
                    )
                )
                merged_entities, merged_relations, stats = merge_incremental_facts(
                    base_entities=base_entities,
                    base_relations=base_relations,
                    extracted_entities=neighborhood.candidate_entities,
                    extracted_relations=neighborhood.candidate_relations,
                    reextract_paths=plan.reextract_paths,
                )
                try:
                    if not merged_entities:
                        raise code_graph_error(
                            CodeGraphReason.MALFORMED_FACT,
                            "incremental merge produced no entities",
                        )
                    assert_relation_endpoints_resolve(
                        entities=merged_entities,
                        relations=merged_relations,
                    )
                except Exception:
                    full = self._with_fallback_notes(
                        self._extractor.extract(
                            self._extraction_request(
                                request,
                                binding=binding,
                                path_includes=request.path_includes,
                            )
                        ),
                        notes=plan.notes
                        + ("incremental merge unsafe; fell back to full extract",),
                    )
                    return full, True, True, empty_stats, ()

                coverage = self._coverage_after_merge(neighborhood)
                if plan.notes:
                    coverage = ExtractionCoverage(
                        status=coverage.status,
                        notes=coverage.notes + plan.notes,
                    )
                merged = ExtractionResult(
                    actual_revision=neighborhood.actual_revision,
                    provider=neighborhood.provider,
                    candidate_entities=merged_entities,
                    candidate_relations=merged_relations,
                    diagnostics=neighborhood.diagnostics,
                    coverage=coverage,
                )
                deleted = deleted_paths_after_refresh(
                    reextract_paths=plan.reextract_paths,
                    base_entities=base_entities,
                    merged_entities=merged_entities,
                )
                return merged, True, False, stats, deleted

            full = self._with_fallback_notes(
                self._extractor.extract(
                    self._extraction_request(
                        request,
                        binding=binding,
                        path_includes=request.path_includes,
                    )
                ),
                notes=plan.notes,
            )
            return full, True, True, empty_stats, ()

        if request.base_snapshot_id is not None and not request.changed_paths:
            # Base without a trusted changed-path set cannot prove a safe
            # neighborhood — fall back to a full extract.
            full = self._with_fallback_notes(
                self._extractor.extract(
                    self._extraction_request(
                        request,
                        binding=binding,
                        path_includes=request.path_includes,
                    )
                ),
                notes=("empty changed_paths; full extraction required",),
            )
            return full, True, True, empty_stats, ()

        full = self._extractor.extract(
            self._extraction_request(
                request, binding=binding, path_includes=request.path_includes
            )
        )
        return full, False, False, empty_stats, ()

    def _extraction_request(
        self,
        request: GraphBuildRequest,
        *,
        binding: RepositoryBinding,
        path_includes: tuple[str, ...],
        changed_paths: tuple[str, ...] = (),
    ) -> ExtractionRequest:
        return ExtractionRequest(
            repository_path=request.repository_path,
            tenant_id=request.tenant_id,
            workspace_object_id=request.workspace_object_id,
            repository_binding_id=binding.binding_id,
            requested_revision=request.requested_revision,
            limits=request.limits,
            path_includes=path_includes,
            path_excludes=request.path_excludes,
            changed_paths=changed_paths,
            base_snapshot_id=request.base_snapshot_id,
        )

    @staticmethod
    def _with_fallback_notes(
        extraction: ExtractionResult,
        *,
        notes: tuple[str, ...],
    ) -> ExtractionResult:
        if not notes:
            return extraction
        merged_notes = tuple(dict.fromkeys((*extraction.coverage.notes, *notes)))
        return ExtractionResult(
            actual_revision=extraction.actual_revision,
            provider=extraction.provider,
            candidate_entities=extraction.candidate_entities,
            candidate_relations=extraction.candidate_relations,
            diagnostics=extraction.diagnostics,
            coverage=ExtractionCoverage(
                status=extraction.coverage.status,
                notes=merged_notes,
            ),
        )

    @staticmethod
    def _coverage_after_merge(neighborhood: ExtractionResult) -> ExtractionCoverage:
        truncated = any(
            item.code in _TRUNCATION_DIAGNOSTIC_CODES
            for item in neighborhood.diagnostics
        )
        if truncated:
            notes = neighborhood.coverage.notes or (
                "neighborhood extract reported truncation diagnostics",
            )
            return ExtractionCoverage(status=CoverageStatus.PARTIAL, notes=notes)
        return ExtractionCoverage(status=CoverageStatus.COMPLETE)

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
        merge_stats: IncrementalMergeStats | None = None,
        incremental: bool = False,
        fallback_full: bool = False,
        deleted_paths: tuple[str, ...] = (),
    ) -> GraphBuildResult:
        stats = merge_stats or IncrementalMergeStats(
            reused_entities=0,
            rebuilt_entities=0,
            reused_relations=0,
            rebuilt_relations=0,
        )
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
            self._stage_sources_for_facts(
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
                reused_entity_count=stats.reused_entities,
                rebuilt_entity_count=stats.rebuilt_entities,
                reused_relation_count=stats.reused_relations,
                rebuilt_relation_count=stats.rebuilt_relations,
                incremental=incremental,
                fallback_full=fallback_full,
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
            if coverage.status is CoverageStatus.PARTIAL:
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
                    reused_entity_count=stats.reused_entities,
                    rebuilt_entity_count=stats.rebuilt_entities,
                    reused_relation_count=stats.reused_relations,
                    rebuilt_relation_count=stats.rebuilt_relations,
                    incremental=incremental,
                    fallback_full=fallback_full,
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
            try:
                source_keys = self._collect_source_keys(
                    entities=entities, relations=relations
                )

                def _point_sources() -> None:
                    for source_id, observation_id, _locator in source_keys:
                        self._intelligence.activate_source_observation_pointer(
                            source_id=source_id,
                            observation_id=observation_id,
                            observed_revision=request.requested_revision,
                            actor_id=request.actor_id,
                            at=request.at,
                        )

                deletion_notes: list[str] = []

                def _record_deletions() -> None:
                    notes = self._invalidate_deleted_sources(
                        request=request,
                        deleted_paths=deleted_paths,
                    )
                    deletion_notes.extend(notes)

                activation_events: list[str] = []

                def _append_activation_events() -> None:
                    completed_event = (
                        M2_EVENT_CODE_GRAPH_BUILD_PARTIAL
                        if coverage.status is CoverageStatus.PARTIAL
                        else M2_EVENT_CODE_GRAPH_BUILD_COMPLETED
                    )
                    activation_events.append(
                        self._append_event(
                            tenant_id=request.tenant_id,
                            event_type=completed_event,
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
                    activation_events.append(
                        self._append_event(
                            tenant_id=request.tenant_id,
                            event_type=M2_EVENT_CODE_GRAPH_SNAPSHOT_ACTIVATED,
                            actor_id=request.actor_id,
                            workspace_object_id=request.workspace_object_id,
                            causation_id=command_id,
                            at=request.at,
                            payload={
                                "snapshot_id": snapshot_id,
                                "repository_binding_id": binding.binding_id,
                                "repository_revision": extraction.actual_revision,
                            },
                        )
                    )

                pending_result = GraphBuildResult(
                    snapshot_id=snapshot_id,
                    extraction_run_id=extraction_run_id,
                    status=SnapshotStatus.ACTIVE,
                    coverage_status=coverage.status,
                    entity_count=len(entities),
                    relation_count=len(relations),
                    actual_revision=extraction.actual_revision,
                    event_types=(),
                    replayed=False,
                    coverage_notes=coverage.notes,
                    diagnostics=tuple(d.code for d in extraction.diagnostics),
                    reused_entity_count=stats.reused_entities,
                    rebuilt_entity_count=stats.rebuilt_entities,
                    reused_relation_count=stats.reused_relations,
                    rebuilt_relation_count=stats.rebuilt_relations,
                    incremental=incremental,
                    fallback_full=fallback_full,
                )

                def _save_success_receipt() -> None:
                    # Receipt is finalized after notes are known; placeholder
                    # identity is enough inside the txn — see post-activate.
                    self._save_receipt(
                        request=request,
                        command_id=command_id,
                        fingerprint=fingerprint,
                        result=pending_result,
                        outcome="accepted",
                        error_code=None,
                        commit=False,
                    )

                with self._intelligence.participate_in_external_transaction():
                    activated = self._graphs.run_activation_unit_of_work(
                        snapshot_id=snapshot_id,
                        tenant_id=request.tenant_id,
                        activated_at=request.at,
                        expected_active_snapshot_id=request.expected_active_snapshot_id,
                        expect_no_active_snapshot=request.expect_no_active_snapshot,
                        steps=(
                            ("point_sources", _point_sources),
                            ("record_deletions", _record_deletions),
                            ("activation_events", _append_activation_events),
                            ("command_receipt", _save_success_receipt),
                        ),
                        fault_before=self._activation_fault_before,
                    )
            except ContentionError as exc:
                if str(exc) != _BASE_SNAPSHOT_NOT_CURRENT:
                    raise
                self._graphs.mark_snapshot_failed(
                    snapshot_id,
                    tenant_id=request.tenant_id,
                    coverage_notes=(_BASE_SNAPSHOT_NOT_CURRENT,),
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
                            "reason": _BASE_SNAPSHOT_NOT_CURRENT,
                            "phase": "activate_cas",
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
                    coverage_notes=(_BASE_SNAPSHOT_NOT_CURRENT,),
                    diagnostics=tuple(d.code for d in extraction.diagnostics),
                    reused_entity_count=stats.reused_entities,
                    rebuilt_entity_count=stats.rebuilt_entities,
                    reused_relation_count=stats.reused_relations,
                    rebuilt_relation_count=stats.rebuilt_relations,
                    incremental=incremental,
                    fallback_full=fallback_full,
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
                reused_entity_count=stats.reused_entities,
                rebuilt_entity_count=stats.rebuilt_entities,
                reused_relation_count=stats.reused_relations,
                rebuilt_relation_count=stats.rebuilt_relations,
                incremental=incremental,
                fallback_full=fallback_full,
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

        event_types.extend(activation_events)
        coverage_notes = tuple(
            dict.fromkeys((*activated.coverage_notes, *deletion_notes))
        )
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
            coverage_notes=coverage_notes,
            diagnostics=tuple(d.code for d in extraction.diagnostics),
            reused_entity_count=stats.reused_entities,
            rebuilt_entity_count=stats.rebuilt_entities,
            reused_relation_count=stats.reused_relations,
            rebuilt_relation_count=stats.rebuilt_relations,
            incremental=incremental,
            fallback_full=fallback_full,
        )
        return result

    def _invalidate_deleted_sources(
        self,
        *,
        request: GraphBuildRequest,
        deleted_paths: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Record deletion observations for registered sources after activate."""

        notes: list[str] = []
        for path in deleted_paths:
            source = self._intelligence.get_source_by_locator(
                tenant_id=request.tenant_id,
                workspace_object_id=request.workspace_object_id,
                locator=path,
            )
            if source is None:
                notes.append(
                    f"deleted path {path!r} had no registered repository-file source"
                )
                continue
            self._intelligence.record_repository_file_removed(
                source.source_id,
                observed_revision=request.requested_revision,
                actor_id=request.actor_id,
                at=request.at,
            )
            notes.append(f"recorded repository file removal for {path!r}")
        return tuple(notes)

    def _collect_source_keys(
        self,
        *,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
    ) -> tuple[tuple[str, str, str], ...]:
        seen: dict[tuple[str, str], str] = {}
        for entity in entities:
            key = (entity.source_id, entity.source_observation_id)
            seen.setdefault(key, entity.repository_relative_path)
        for relation in relations:
            key = (relation.evidence_source_id, relation.evidence_observation_id)
            if key not in seen:
                locator = next(
                    (
                        e.repository_relative_path
                        for e in entities
                        if e.source_id == relation.evidence_source_id
                    ),
                    f"evidence/{relation.evidence_source_id}",
                )
                seen[key] = locator
        return tuple(
            (source_id, observation_id, locator)
            for (source_id, observation_id), locator in seen.items()
        )

    def _stage_sources_for_facts(
        self,
        *,
        request: GraphBuildRequest,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
    ) -> None:
        """Stage immutable observation rows without flipping current pointers."""

        for source_id, observation_id, locator in self._collect_source_keys(
            entities=entities, relations=relations
        ):
            self._intelligence.stage_repository_file_source_observation(
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
                "expected_active_snapshot_id": request.expected_active_snapshot_id,
                "expect_no_active_snapshot": request.expect_no_active_snapshot,
                "path_includes": list(request.path_includes),
                "path_excludes": list(request.path_excludes),
                "changed_paths": list(request.changed_paths),
                "limits": {
                    "max_files": request.limits.max_files,
                    "max_file_bytes": request.limits.max_file_bytes,
                    "max_entities": request.limits.max_entities,
                    "max_relations": request.limits.max_relations,
                    "max_seconds": request.limits.max_seconds,
                },
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
        commit: bool = True,
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
        if commit:
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
