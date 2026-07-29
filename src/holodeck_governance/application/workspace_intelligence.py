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

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.workspace.intelligence import (
    AUTHORITY_COVERING_MODULE_KEYS,
    INTELLIGENCE_CURATE_PERMISSION,
    ContextItem,
    ContextModule,
    Contradiction,
    DecisionOutcome,
    GapStatus,
    KnowledgeGap,
    ModelRevisionStatus,
    ModuleApprovalStatus,
    ObservedSourcePath,
    ReadinessLevel,
    SourceObservation,
    SourceRefreshObservation,
    StaleStatus,
    TrustClass,
    WorkspaceCurationProposal,
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    assert_trust_promotion_decision_authorizes,
    derive_evidenced_maximum_readiness,
    invent_sources_from_observations,
    module_ids_depending_on_source,
    readiness_level_index,
    select_preferred_model_revision,
    trust_promotion_requires_human_decision,
    validate_curation_proposal,
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


@dataclass(frozen=True, slots=True)
class CurationActivationResult:
    """Outcome of activate_curation in one repository transaction."""

    approved_model: WorkspaceModelRevision
    approved_modules: tuple[ContextModule, ...]
    promoted_sources: tuple[WorkspaceSource, ...]
    readiness: WorkspaceReadinessAssessment
    event_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RefreshSourcesResult:
    """Outcome of refresh_sources with selective stale propagation."""

    refreshed_source_ids: tuple[str, ...]
    skipped_unchanged: tuple[str, ...]
    staled_module_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceIntelligenceSnapshot:
    """Cohesive read-only intelligence view for a workspace."""

    model: WorkspaceModelRevision | None
    sources: tuple[WorkspaceSource, ...]
    modules: tuple[ContextModule, ...]
    open_gaps: tuple[KnowledgeGap, ...]
    latest_readiness: WorkspaceReadinessAssessment | None
    stale_source_ids: tuple[str, ...]
    stale_module_ids: tuple[str, ...]


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

    def list_source_observations(
        self, source_id: str, *, tenant_id: str
    ) -> list[SourceObservation]: ...

    def get_source_observation(
        self, observation_id: str
    ) -> SourceObservation | None: ...

    def update_source_trust(
        self,
        source_id: str,
        *,
        tenant_id: str,
        to_trust: TrustClass,
        actor_id: str,
        at: datetime,
        promotion_decision_id: str | None = None,
    ) -> WorkspaceSource: ...

    def get_actor(self, actor_id: str) -> Actor | None: ...

    def mark_source_stale(
        self,
        source_id: str,
        *,
        tenant_id: str,
        dependent_module_ids: tuple[str, ...],
        actor_id: str,
        at: datetime,
    ) -> WorkspaceSource: ...

    def apply_source_refreshes(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        refreshes: Sequence[
            tuple[str, str, str | None, tuple[str, ...]]
        ],
        actor_id: str,
        at: datetime,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]: ...

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

    def require_workspace_object(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> None: ...

    def activate_curation(
        self,
        proposal: WorkspaceCurationProposal,
    ) -> tuple[
        WorkspaceModelRevision,
        tuple[ContextModule, ...],
        tuple[WorkspaceSource, ...],
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

    def list_source_observations(
        self, source_id: str, *, tenant_id: str
    ) -> list[SourceObservation]:
        return self.repository.list_source_observations(
            source_id, tenant_id=tenant_id
        )

    def get_source_observation(
        self, observation_id: str
    ) -> SourceObservation | None:
        return self.repository.get_source_observation(observation_id)

    def update_source_trust(
        self,
        source_id: str,
        *,
        tenant_id: str,
        to_trust: TrustClass,
        actor_id: str,
        at: datetime,
        promotion_decision_id: str | None = None,
    ) -> WorkspaceSource:
        source = self.repository.get_source(source_id)
        if source is None:
            raise NotFoundGovernanceError(f"unknown source {source_id}")
        if source.tenant_id != tenant_id:
            raise CrossTenantAccessError("source tenant mismatch")
        if trust_promotion_requires_human_decision(source.trust_class, to_trust):
            self._require_human_promotion_decision(
                decision_id=promotion_decision_id,
                source=source,
            )
        return self.repository.update_source_trust(
            source_id,
            tenant_id=tenant_id,
            to_trust=to_trust,
            actor_id=actor_id,
            at=at,
            promotion_decision_id=promotion_decision_id,
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

    def propagate_source_stale(
        self,
        source_id: str,
        *,
        tenant_id: str,
        actor_id: str,
        at: datetime,
    ) -> WorkspaceSource:
        """Mark a source and every module that lists it in ``source_ids`` stale."""

        if not self.repository.actor_has_permission(
            tenant_id=tenant_id,
            actor_id=actor_id,
            permission=INTELLIGENCE_CURATE_PERMISSION,
            at=at,
        ):
            raise MissingAuthorityError(
                "actor lacks workspace.intelligence.curate authority"
            )
        source = self.repository.get_source(source_id)
        if source is None:
            raise NotFoundGovernanceError(f"unknown source {source_id}")
        if source.tenant_id != tenant_id:
            raise CrossTenantAccessError("source tenant mismatch")
        modules = self.repository.list_context_modules(
            source.workspace_object_id, tenant_id=tenant_id
        )
        dependent_ids = module_ids_depending_on_source(modules, source_id)
        return self.repository.mark_source_stale(
            source_id,
            tenant_id=tenant_id,
            dependent_module_ids=dependent_ids,
            actor_id=actor_id,
            at=at,
        )

    def refresh_sources(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        observations: Sequence[SourceRefreshObservation],
        actor_id: str,
        at: datetime,
    ) -> RefreshSourcesResult:
        """Update observed revisions and selectively stale dependent modules.

        Unknown ``source_id`` / locator raises ``NotFoundGovernanceError``.
        Same-revision observations are skipped without side effects.
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
        self.repository.require_workspace_object(
            workspace_object_id, tenant_id=tenant_id
        )
        modules = self.repository.list_context_modules(
            workspace_object_id, tenant_id=tenant_id
        )
        refreshed: list[str] = []
        skipped: list[str] = []
        refreshes: list[tuple[str, str, str | None, tuple[str, ...]]] = []
        staled: set[str] = set()
        for observation in observations:
            source = self._resolve_refresh_source(
                observation,
                tenant_id=tenant_id,
                workspace_object_id=workspace_object_id,
            )
            if source.observed_revision == observation.new_observed_revision:
                skipped.append(source.source_id)
                continue
            dependent_ids = module_ids_depending_on_source(
                modules, source.source_id
            )
            refreshes.append(
                (
                    source.source_id,
                    observation.new_observed_revision,
                    observation.content_hash,
                    dependent_ids,
                )
            )
            refreshed.append(source.source_id)
            staled.update(dependent_ids)
        if refreshes:
            _, repo_staled = self.repository.apply_source_refreshes(
                workspace_object_id,
                tenant_id=tenant_id,
                refreshes=refreshes,
                actor_id=actor_id,
                at=at,
            )
            staled.update(repo_staled)
        return RefreshSourcesResult(
            refreshed_source_ids=tuple(refreshed),
            skipped_unchanged=tuple(skipped),
            staled_module_ids=tuple(sorted(staled)),
        )

    def _resolve_refresh_source(
        self,
        observation: SourceRefreshObservation,
        *,
        tenant_id: str,
        workspace_object_id: str,
    ) -> WorkspaceSource:
        if observation.source_id is not None:
            source = self.repository.get_source(observation.source_id)
            if source is None:
                raise NotFoundGovernanceError(
                    f"unknown source {observation.source_id}"
                )
            if source.tenant_id != tenant_id:
                raise CrossTenantAccessError("source tenant mismatch")
            if source.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "source workspace does not match refresh target"
                )
            return source
        assert observation.locator is not None
        source = self.repository.get_source_by_locator(
            tenant_id=tenant_id,
            workspace_object_id=workspace_object_id,
            locator=observation.locator,
        )
        if source is None:
            raise NotFoundGovernanceError(
                f"unknown source locator {observation.locator}"
            )
        return source

    def query_workspace_intelligence(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        model_revision_id: str | None = None,
    ) -> WorkspaceIntelligenceSnapshot:
        """Read-only cohesive snapshot; does not require curate permission."""

        self.repository.require_workspace_object(
            workspace_object_id, tenant_id=tenant_id
        )
        revisions = self.repository.list_model_revisions(
            workspace_object_id, tenant_id=tenant_id
        )
        model = select_preferred_model_revision(
            revisions, model_revision_id=model_revision_id
        )
        if model_revision_id is not None and model is None:
            raise NotFoundGovernanceError(
                f"unknown model revision {model_revision_id}"
            )
        sources = tuple(
            self.repository.list_sources(workspace_object_id, tenant_id=tenant_id)
        )
        modules = tuple(
            self.repository.list_context_modules(
                workspace_object_id, tenant_id=tenant_id
            )
        )
        open_gaps = tuple(
            self.repository.list_knowledge_gaps(
                workspace_object_id, tenant_id=tenant_id, status=GapStatus.OPEN
            )
        )
        latest_readiness = self.repository.get_latest_readiness(
            workspace_object_id, tenant_id=tenant_id
        )
        return WorkspaceIntelligenceSnapshot(
            model=model,
            sources=sources,
            modules=modules,
            open_gaps=open_gaps,
            latest_readiness=latest_readiness,
            stale_source_ids=tuple(
                source.source_id
                for source in sources
                if source.stale_status is StaleStatus.STALE
            ),
            stale_module_ids=tuple(
                module.module_id
                for module in modules
                if module.freshness is StaleStatus.STALE
            ),
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

    def validate_curation(
        self,
        proposal: WorkspaceCurationProposal,
    ) -> None:
        """Load records and reject structurally or referentially invalid proposals."""

        self.repository.require_workspace_object(
            proposal.workspace_object_id, tenant_id=proposal.tenant_id
        )
        model = self.repository.get_model_revision(proposal.model_revision_id)
        if model is None:
            raise NotFoundGovernanceError(
                f"unknown model revision {proposal.model_revision_id}"
            )
        if model.tenant_id != proposal.tenant_id:
            raise CrossTenantAccessError("model revision tenant mismatch")
        if model.workspace_object_id != proposal.workspace_object_id:
            raise MalformedCommandError(
                "model revision workspace does not match curation proposal"
            )
        if model.status is not ModelRevisionStatus.PROPOSED:
            raise MalformedCommandError(
                "only proposed model revisions can be activated"
            )

        current_trust: dict[str, TrustClass] = {}
        sources_by_id: dict[str, WorkspaceSource] = {}
        for promotion in proposal.trust_promotions:
            source = self.repository.get_source(promotion.source_id)
            if source is None:
                raise NotFoundGovernanceError(
                    f"unknown source {promotion.source_id}"
                )
            if source.tenant_id != proposal.tenant_id:
                raise CrossTenantAccessError("source tenant mismatch")
            if source.workspace_object_id != proposal.workspace_object_id:
                raise MalformedCommandError(
                    "source workspace does not match curation proposal"
                )
            current_trust[promotion.source_id] = source.trust_class
            sources_by_id[promotion.source_id] = source

        modules_to_approve: list[ContextModule] = []
        for module_id in proposal.module_ids_to_approve:
            module = self.repository.get_context_module(module_id)
            if module is None:
                raise NotFoundGovernanceError(f"unknown context module {module_id}")
            if module.tenant_id != proposal.tenant_id:
                raise CrossTenantAccessError("context module tenant mismatch")
            if module.workspace_object_id != proposal.workspace_object_id:
                raise MalformedCommandError(
                    "context module workspace does not match curation proposal"
                )
            if module.approval_status is not ModuleApprovalStatus.PROPOSED:
                raise MalformedCommandError(
                    "only proposed context modules can be approved"
                )
            modules_to_approve.append(module)

        actual_open = {
            gap.gap_id
            for gap in self.repository.list_knowledge_gaps(
                proposal.workspace_object_id,
                tenant_id=proposal.tenant_id,
                status=GapStatus.OPEN,
            )
        }
        if set(proposal.open_gap_ids) != actual_open:
            raise MalformedCommandError(
                "open_gap_ids must exactly match open knowledge gaps"
            )

        for promotion in proposal.trust_promotions:
            source = sources_by_id[promotion.source_id]
            if trust_promotion_requires_human_decision(
                source.trust_class, promotion.to_trust
            ):
                self._require_human_promotion_decision(
                    decision_id=promotion.decision_id,
                    source=source,
                )

        human_authorized = self._resolve_human_authorized_readiness(proposal)
        evidenced = self._derive_evidenced_maximum_for_proposal(
            proposal,
            modules_to_approve=modules_to_approve,
            sources_by_id=sources_by_id,
            human_authorized_readiness=human_authorized,
        )
        validate_curation_proposal(
            proposal,
            evidenced_maximum=evidenced,
            current_trust_by_source_id=current_trust,
        )

    def _resolve_human_authorized_readiness(
        self, proposal: WorkspaceCurationProposal
    ) -> ReadinessLevel | None:
        if proposal.readiness_decision_id is None:
            return None
        decision = self.repository.get_workspace_decision(
            proposal.readiness_decision_id
        )
        if decision is None:
            raise NotFoundGovernanceError(
                f"unknown workspace decision {proposal.readiness_decision_id}"
            )
        if decision.tenant_id != proposal.tenant_id:
            raise CrossTenantAccessError("readiness decision tenant mismatch")
        if decision.workspace_object_id != proposal.workspace_object_id:
            raise MalformedCommandError(
                "readiness decision workspace does not match curation proposal"
            )
        if decision.outcome is not DecisionOutcome.APPROVED:
            raise MalformedCommandError(
                "readiness requires an approved workspace decision"
            )
        if decision.subject_revision_id not in {
            proposal.model_revision_id,
            proposal.assessment_id or "",
        }:
            raise MalformedCommandError(
                "readiness decision subject must be the model revision or assessment"
            )
        actor = self.repository.get_actor(decision.authorized_actor_id)
        if actor is None:
            raise NotFoundGovernanceError(
                f"unknown actor {decision.authorized_actor_id}"
            )
        if actor.kind is not ActorKind.HUMAN:
            raise MalformedCommandError(
                "readiness decision authorizing actor must be human"
            )
        return proposal.claimed_readiness_level

    def _derive_evidenced_maximum_for_proposal(
        self,
        proposal: WorkspaceCurationProposal,
        *,
        modules_to_approve: Sequence[ContextModule],
        sources_by_id: dict[str, WorkspaceSource],
        human_authorized_readiness: ReadinessLevel | None,
    ) -> ReadinessLevel:
        existing_sources = self.repository.list_sources(
            proposal.workspace_object_id, tenant_id=proposal.tenant_id
        )
        existing_modules = self.repository.list_context_modules(
            proposal.workspace_object_id, tenant_id=proposal.tenant_id
        )
        approved_existing = [
            module
            for module in existing_modules
            if module.approval_status is ModuleApprovalStatus.APPROVED
            and module.module_id not in proposal.module_ids_to_approve
        ]
        approving_modules = list(modules_to_approve) + approved_existing
        approved_or_approving_count = len(approving_modules)

        trust_after: dict[str, TrustClass] = {
            source.source_id: source.trust_class for source in existing_sources
        }
        for promotion in proposal.trust_promotions:
            trust_after[promotion.source_id] = promotion.to_trust
        for source_id, source in sources_by_id.items():
            trust_after.setdefault(source_id, source.trust_class)

        has_ia = any(
            trust is TrustClass.INSTRUCTION_AUTHORITY
            for trust in trust_after.values()
        )
        has_authority_module = any(
            module.module_key in AUTHORITY_COVERING_MODULE_KEYS
            for module in approving_modules
        )
        return derive_evidenced_maximum_readiness(
            has_model=True,
            model_approved_or_approving=True,
            has_sources=bool(existing_sources),
            approved_or_approving_module_count=approved_or_approving_count,
            open_gap_count=len(proposal.open_gap_ids),
            has_governed_authority_basis=has_ia or has_authority_module,
            human_authorized_readiness=human_authorized_readiness,
        )

    def activate_curation(
        self,
        proposal: WorkspaceCurationProposal,
    ) -> CurationActivationResult:
        """Approve model/modules, apply trust promotions, and store readiness."""

        if not self.repository.actor_has_permission(
            tenant_id=proposal.tenant_id,
            actor_id=proposal.actor_id,
            permission=INTELLIGENCE_CURATE_PERMISSION,
            at=proposal.at,
        ):
            raise MissingAuthorityError(
                "actor lacks workspace.intelligence.curate authority"
            )
        self.validate_curation(proposal)
        (
            approved_model,
            approved_modules,
            promoted_sources,
            readiness,
            event_types,
        ) = self.repository.activate_curation(proposal)
        return CurationActivationResult(
            approved_model=approved_model,
            approved_modules=approved_modules,
            promoted_sources=promoted_sources,
            readiness=readiness,
            event_types=event_types,
        )

    def _require_human_promotion_decision(
        self,
        *,
        decision_id: str | None,
        source: WorkspaceSource,
    ) -> None:
        if decision_id is None:
            raise MalformedCommandError(
                "trust elevation requires an approved human workspace decision_id"
            )
        decision = self.repository.get_workspace_decision(decision_id)
        if decision is None:
            raise NotFoundGovernanceError(f"unknown workspace decision {decision_id}")
        actor = self.repository.get_actor(decision.authorized_actor_id)
        if actor is None:
            raise NotFoundGovernanceError(
                f"unknown actor {decision.authorized_actor_id}"
            )
        assert_trust_promotion_decision_authorizes(
            decision=decision,
            actor=actor,
            source=source,
        )
