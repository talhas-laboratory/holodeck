"""Application seam for governed workspace intelligence operations (M2-013+).

Thin adapter over the storage repository. It preserves the M1
domain/application/storage separation: the domain contracts stay pure, the
repository owns tenant isolation and immutability, and this service exposes a
stable surface for HTTP/CLI adapters and future agent adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from holodeck_governance.domain.errors import MissingAuthorityError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    ContextItem,
    ContextModule,
    Contradiction,
    GapStatus,
    KnowledgeGap,
    ObservedSourcePath,
    StaleStatus,
    TrustClass,
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    invent_sources_from_observations,
)


@dataclass(frozen=True, slots=True)
class OnboardedIntelligence:
    """Result of a single-transaction onboarding write."""

    model_revision: WorkspaceModelRevision
    sources: tuple[WorkspaceSource, ...]
    modules: tuple[ContextModule, ...]
    items: tuple[ContextItem, ...]
    gaps: tuple[KnowledgeGap, ...]
    readiness: WorkspaceReadinessAssessment
    event_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceDiscoveryResult:
    """Outcome of discover_and_register_sources.

    Natural-key conflicts (tenant, workspace, locator) skip the existing source
    rather than failing the batch — rediscovery is idempotent.
    """

    registered_source_ids: tuple[str, ...]
    skipped_existing_source_ids: tuple[str, ...]

    @property
    def registered_count(self) -> int:
        return len(self.registered_source_ids)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_existing_source_ids)


class WorkspaceIntelligenceRepositoryPort(Protocol):
    def actor_has_permission(
        self, *, tenant_id: str, actor_id: str, permission: str, at: datetime
    ) -> bool: ...

    def save_model_revision(self, revision: WorkspaceModelRevision) -> None: ...

    def get_model_revision(
        self, model_revision_id: str
    ) -> WorkspaceModelRevision | None: ...

    def list_model_revisions(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceModelRevision]: ...

    def approve_model_revision(
        self,
        model_revision_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> WorkspaceModelRevision: ...

    def register_source(self, source: WorkspaceSource) -> None: ...

    def get_source(self, source_id: str) -> WorkspaceSource | None: ...

    def get_source_by_locator(
        self, *, tenant_id: str, workspace_object_id: str, locator: str
    ) -> WorkspaceSource | None: ...

    def list_sources(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceSource]: ...

    def update_source_trust(
        self,
        source_id: str,
        *,
        tenant_id: str,
        to_trust: TrustClass,
        actor_id: str,
        authorized_human_promotion: bool,
        at: datetime,
    ) -> WorkspaceSource: ...

    def mark_source_stale(
        self,
        source_id: str,
        *,
        tenant_id: str,
        dependent_module_ids: tuple[str, ...],
        actor_id: str,
        at: datetime,
    ) -> WorkspaceSource: ...

    def save_context_item(self, item: ContextItem) -> None: ...

    def get_context_item(self, item_id: str) -> ContextItem | None: ...

    def save_context_module(self, module: ContextModule) -> None: ...

    def get_context_module(self, module_id: str) -> ContextModule | None: ...

    def list_context_modules(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[ContextModule]: ...

    def approve_context_module(
        self,
        module_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> ContextModule: ...

    def save_knowledge_gap(self, gap: KnowledgeGap) -> None: ...

    def get_knowledge_gap(self, gap_id: str) -> KnowledgeGap | None: ...

    def list_knowledge_gaps(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        status: GapStatus | None = None,
    ) -> list[KnowledgeGap]: ...

    def resolve_knowledge_gap(
        self,
        gap_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> KnowledgeGap: ...

    def save_contradiction(self, contradiction: Contradiction) -> None: ...

    def get_contradiction(self, contradiction_id: str) -> Contradiction | None: ...

    def resolve_contradiction(
        self,
        contradiction_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> Contradiction: ...

    def save_workspace_decision(self, decision: WorkspaceDecision) -> None: ...

    def get_workspace_decision(
        self, decision_id: str
    ) -> WorkspaceDecision | None: ...

    def save_readiness_assessment(
        self, assessment: WorkspaceReadinessAssessment
    ) -> None: ...

    def get_readiness_assessment(
        self, assessment_id: str
    ) -> WorkspaceReadinessAssessment | None: ...

    def get_latest_readiness(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> WorkspaceReadinessAssessment | None: ...

    def onboard_intelligence(
        self,
        *,
        model: WorkspaceModelRevision,
        sources: tuple[WorkspaceSource, ...],
        modules: tuple[ContextModule, ...],
        gaps: tuple[KnowledgeGap, ...],
        readiness: WorkspaceReadinessAssessment,
        actor_id: str,
        at: datetime,
        items: tuple[ContextItem, ...] = (),
    ) -> tuple[
        WorkspaceModelRevision,
        tuple[WorkspaceSource, ...],
        tuple[ContextModule, ...],
        tuple[ContextItem, ...],
        tuple[KnowledgeGap, ...],
        WorkspaceReadinessAssessment,
        tuple[str, ...],
    ]: ...


@dataclass(frozen=True, slots=True)
class WorkspaceIntelligenceApplicationService:
    """Governed application surface for workspace intelligence records."""

    repository: WorkspaceIntelligenceRepositoryPort

    def onboard(
        self,
        *,
        model: WorkspaceModelRevision,
        sources: tuple[WorkspaceSource, ...],
        modules: tuple[ContextModule, ...],
        gaps: tuple[KnowledgeGap, ...],
        readiness: WorkspaceReadinessAssessment,
        actor_id: str,
        at: datetime,
        items: tuple[ContextItem, ...] = (),
    ) -> OnboardedIntelligence:
        (
            model_revision,
            stored_sources,
            stored_modules,
            stored_items,
            stored_gaps,
            stored_readiness,
            event_types,
        ) = self.repository.onboard_intelligence(
            model=model,
            sources=sources,
            modules=modules,
            gaps=gaps,
            readiness=readiness,
            actor_id=actor_id,
            at=at,
            items=items,
        )
        return OnboardedIntelligence(
            model_revision=model_revision,
            sources=stored_sources,
            modules=stored_modules,
            items=stored_items,
            gaps=stored_gaps,
            readiness=stored_readiness,
            event_types=event_types,
        )

    def save_model_revision(
        self, revision: WorkspaceModelRevision
    ) -> WorkspaceModelRevision:
        self.repository.save_model_revision(revision)
        return revision

    def get_model_revision(
        self, model_revision_id: str
    ) -> WorkspaceModelRevision | None:
        return self.repository.get_model_revision(model_revision_id)

    def list_model_revisions(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceModelRevision]:
        return self.repository.list_model_revisions(
            workspace_object_id, tenant_id=tenant_id
        )

    def approve_model_revision(
        self,
        model_revision_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> WorkspaceModelRevision:
        return self.repository.approve_model_revision(
            model_revision_id,
            tenant_id=tenant_id,
            approved_by_actor_id=approved_by_actor_id,
            approved_at=approved_at,
        )

    def register_source(self, source: WorkspaceSource) -> WorkspaceSource:
        self.repository.register_source(source)
        return source

    def discover_and_register_sources(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        observations: Sequence[ObservedSourcePath],
        actor_id: str,
        at: datetime,
        owner_actor_id: str | None = None,
    ) -> SourceDiscoveryResult:
        """Classify observed paths and register invented sources.

        Requires ``workspace.intelligence.curate``. Discovery never sets
        ``instruction_authority``. When a locator is already registered for the
        workspace natural key, the existing source is skipped (idempotent
        rediscovery) instead of failing the whole batch.
        """

        if not self.repository.actor_has_permission(
            tenant_id=tenant_id,
            actor_id=actor_id,
            permission=INTELLIGENCE_CURATE_PERMISSION,
            at=at,
        ):
            raise MissingAuthorityError(
                "actor lacks workspace.intelligence.curate authority"
            )

        owner = owner_actor_id or actor_id
        candidates = invent_sources_from_observations(tuple(observations))
        registered: list[str] = []
        skipped: list[str] = []
        for candidate in candidates:
            existing = self.repository.get_source_by_locator(
                tenant_id=tenant_id,
                workspace_object_id=workspace_object_id,
                locator=candidate.locator,
            )
            if existing is not None:
                skipped.append(existing.source_id)
                continue
            source = WorkspaceSource(
                source_id=generate_uuidv7(),
                tenant_id=tenant_id,
                workspace_object_id=workspace_object_id,
                source_type=candidate.source_type,
                locator=candidate.locator,
                observed_revision=candidate.observed_revision,
                trust_class=candidate.trust_class,
                owner_actor_id=owner,
                sensitivity=candidate.sensitivity,
                refresh_policy=candidate.refresh_policy,
                observed_at=at,
                stale_status=StaleStatus.FRESH,
                created_at=at,
                created_by_actor_id=actor_id,
                instruction_authority=False,
                content_hash=candidate.content_hash,
                module_tags=candidate.module_tags,
            )
            self.repository.register_source(source)
            registered.append(source.source_id)
        return SourceDiscoveryResult(
            registered_source_ids=tuple(registered),
            skipped_existing_source_ids=tuple(skipped),
        )

    def get_source(self, source_id: str) -> WorkspaceSource | None:
        return self.repository.get_source(source_id)

    def list_sources(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceSource]:
        return self.repository.list_sources(workspace_object_id, tenant_id=tenant_id)

    def update_source_trust(
        self,
        source_id: str,
        *,
        tenant_id: str,
        to_trust: TrustClass,
        actor_id: str,
        authorized_human_promotion: bool,
        at: datetime,
    ) -> WorkspaceSource:
        return self.repository.update_source_trust(
            source_id,
            tenant_id=tenant_id,
            to_trust=to_trust,
            actor_id=actor_id,
            authorized_human_promotion=authorized_human_promotion,
            at=at,
        )

    def mark_source_stale(
        self,
        source_id: str,
        *,
        tenant_id: str,
        dependent_module_ids: tuple[str, ...],
        actor_id: str,
        at: datetime,
    ) -> WorkspaceSource:
        return self.repository.mark_source_stale(
            source_id,
            tenant_id=tenant_id,
            dependent_module_ids=dependent_module_ids,
            actor_id=actor_id,
            at=at,
        )

    def save_context_item(self, item: ContextItem) -> ContextItem:
        self.repository.save_context_item(item)
        return item

    def get_context_item(self, item_id: str) -> ContextItem | None:
        return self.repository.get_context_item(item_id)

    def save_context_module(self, module: ContextModule) -> ContextModule:
        self.repository.save_context_module(module)
        return module

    def get_context_module(self, module_id: str) -> ContextModule | None:
        return self.repository.get_context_module(module_id)

    def list_context_modules(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[ContextModule]:
        return self.repository.list_context_modules(
            workspace_object_id, tenant_id=tenant_id
        )

    def approve_context_module(
        self,
        module_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> ContextModule:
        return self.repository.approve_context_module(
            module_id,
            tenant_id=tenant_id,
            approved_by_actor_id=approved_by_actor_id,
            approved_at=approved_at,
        )

    def save_knowledge_gap(self, gap: KnowledgeGap) -> KnowledgeGap:
        self.repository.save_knowledge_gap(gap)
        return gap

    def get_knowledge_gap(self, gap_id: str) -> KnowledgeGap | None:
        return self.repository.get_knowledge_gap(gap_id)

    def list_knowledge_gaps(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        status: GapStatus | None = None,
    ) -> list[KnowledgeGap]:
        return self.repository.list_knowledge_gaps(
            workspace_object_id, tenant_id=tenant_id, status=status
        )

    def resolve_knowledge_gap(
        self,
        gap_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> KnowledgeGap:
        return self.repository.resolve_knowledge_gap(
            gap_id,
            tenant_id=tenant_id,
            resolution_reference_id=resolution_reference_id,
            actor_id=actor_id,
            at=at,
        )

    def save_contradiction(self, contradiction: Contradiction) -> Contradiction:
        self.repository.save_contradiction(contradiction)
        return contradiction

    def get_contradiction(self, contradiction_id: str) -> Contradiction | None:
        return self.repository.get_contradiction(contradiction_id)

    def resolve_contradiction(
        self,
        contradiction_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> Contradiction:
        return self.repository.resolve_contradiction(
            contradiction_id,
            tenant_id=tenant_id,
            resolution_reference_id=resolution_reference_id,
            actor_id=actor_id,
            at=at,
        )

    def save_workspace_decision(
        self, decision: WorkspaceDecision
    ) -> WorkspaceDecision:
        self.repository.save_workspace_decision(decision)
        return decision

    def get_workspace_decision(
        self, decision_id: str
    ) -> WorkspaceDecision | None:
        return self.repository.get_workspace_decision(decision_id)

    def save_readiness_assessment(
        self, assessment: WorkspaceReadinessAssessment
    ) -> WorkspaceReadinessAssessment:
        self.repository.save_readiness_assessment(assessment)
        return assessment

    def get_readiness_assessment(
        self, assessment_id: str
    ) -> WorkspaceReadinessAssessment | None:
        return self.repository.get_readiness_assessment(assessment_id)

    def get_latest_readiness(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> WorkspaceReadinessAssessment | None:
        return self.repository.get_latest_readiness(
            workspace_object_id, tenant_id=tenant_id
        )
