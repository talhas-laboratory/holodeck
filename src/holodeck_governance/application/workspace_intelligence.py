"""Application seam for governed workspace intelligence operations (M2-013).

Thin adapter over the storage repository. It preserves the M1
domain/application/storage separation: the domain contracts stay pure, the
repository owns tenant isolation and immutability, and this service exposes a
stable surface for HTTP/CLI adapters and future agent adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from holodeck_governance.domain.workspace.intelligence import (
    ContextItem,
    ContextModule,
    Contradiction,
    GapStatus,
    KnowledgeGap,
    TrustClass,
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
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
