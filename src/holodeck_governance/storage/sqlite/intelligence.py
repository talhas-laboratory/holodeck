"""SQLite persistence for governed workspace intelligence records (M2-013).

Additive persistence over the M1 governance schema. Domain contracts stay pure;
this adapter validates tenant isolation, curate authority, and immutability, then
persists model revisions, sources, context items/modules, gaps, contradictions,
decisions, and readiness assessments. Mutating operations require the
``workspace.intelligence.curate`` permission and emit durable M2 domain events.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Sequence

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    IdempotencyConflictError,
    MalformedCommandError,
    MissingAuthorityError,
    NotFoundGovernanceError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.workspace.intelligence import (
    INTELLIGENCE_CURATE_PERMISSION,
    M2_EVENT_CONTEXT_MODULE_STALE,
    M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED,
    M2_EVENT_KNOWLEDGE_GAP_CREATED,
    M2_EVENT_MODEL_APPROVED,
    M2_EVENT_MODEL_PROPOSED,
    M2_EVENT_READINESS_ASSESSED,
    M2_EVENT_SOURCE_REGISTERED,
    M2_EVENT_SOURCE_STALE,
    ContextItem,
    ContextItemType,
    ContextModule,
    Contradiction,
    ContradictionStatus,
    DecisionOutcome,
    GapStatus,
    IntentSeed,
    KnowledgeGap,
    ModelRevisionStatus,
    ModelSectionState,
    ModuleApprovalStatus,
    ReadinessLevel,
    SectionCertainty,
    SourceType,
    StaleStatus,
    TrustClass,
    ValidationStatus,
    WorkspaceCurationProposal,
    WorkspaceDecision,
    WorkspaceModelRevision,
    WorkspaceReadinessAssessment,
    WorkspaceSource,
    assert_trust_promotion_allowed,
)
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.repos import SqliteDomainEventRepository

M2_INTELLIGENCE_EVENT_SCHEMA_VERSION = "m2.workspace.intelligence.event.v1"

def _insert_immutable(conn: sqlite3.Connection, sql: str, params: tuple) -> None:
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        raise RevisionImmutableError(
            "workspace intelligence record already exists and cannot be overwritten"
        ) from exc


def _json_list(values: tuple[str, ...]) -> str:
    return json.dumps(list(values))


def _read_list(raw: object) -> tuple[str, ...]:
    return tuple(json.loads(str(raw)))


class SqliteWorkspaceIntelligenceRepository:
    """Governed persistence seam for workspace intelligence records."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._tx_depth = 0
        migrate_governance(conn)
        self._conn.execute("PRAGMA foreign_keys = ON")

    # -- transaction helpers (mirrors collaboration repository) --------------

    def _commit_write(self) -> None:
        if self._tx_depth == 0:
            self._conn.commit()

    def _begin_write(self) -> str | None:
        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        self._conn.execute("BEGIN IMMEDIATE")
        self._tx_depth += 1
        return previous

    def _commit_txn(self, previous: str | None) -> None:
        self._conn.execute("COMMIT")
        self._tx_depth = max(0, self._tx_depth - 1)
        self._conn.isolation_level = previous

    def _rollback_txn(self, previous: str | None) -> None:
        self._conn.execute("ROLLBACK")
        self._tx_depth = max(0, self._tx_depth - 1)
        self._conn.isolation_level = previous

    # -- authority / tenant guards -------------------------------------------

    def actor_has_permission(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        permission: str,
        at: datetime,
    ) -> bool:
        """Tenant-scoped role permission check for an explicit capability."""

        from holodeck_governance.domain.authority.assignments import (
            RoleAssignment,
            assignment_is_active,
        )

        if not permission.strip():
            raise MalformedCommandError("permission is required")
        rows = self._conn.execute(
            """
            SELECT a.*, p.permissions_json
            FROM gov_role_assignments a
            JOIN gov_role_profiles p
              ON p.role_object_id = a.role_object_id AND p.revision = a.role_revision
            WHERE a.tenant_id = ? AND a.actor_id = ?
            """,
            (tenant_id, actor_id),
        ).fetchall()
        for row in rows:
            assignment = RoleAssignment(
                assignment_id=str(row["assignment_id"]),
                tenant_id=str(row["tenant_id"]),
                actor_id=str(row["actor_id"]),
                role_object_id=str(row["role_object_id"]),
                role_revision=int(row["role_revision"]),
                workspace_object_id=row["workspace_object_id"],
                jurisdiction_key=str(row["jurisdiction_key"]),
                jurisdiction_value=str(row["jurisdiction_value"]),
                effective_from=datetime.fromisoformat(str(row["effective_from"])),
                created_at=datetime.fromisoformat(str(row["created_at"])),
                created_by_actor_id=str(row["created_by_actor_id"]),
                effective_until=(
                    datetime.fromisoformat(str(row["effective_until"]))
                    if row["effective_until"] is not None
                    else None
                ),
                schema_version=str(row["schema_version"]),
            )
            if not assignment_is_active(assignment, at=at):
                continue
            if assignment.jurisdiction_key not in {"tenant", "*"}:
                continue
            permissions = set(json.loads(str(row["permissions_json"])))
            if permission in permissions or "*" in permissions:
                return True
        return False

    def get_actor(self, actor_id: str) -> Actor | None:
        row = self._conn.execute(
            "SELECT * FROM gov_actors WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            return None
        return Actor(
            actor_id=str(row["actor_id"]),
            tenant_id=str(row["tenant_id"]),
            kind=ActorKind(str(row["kind"])),
            display_name=str(row["display_name"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            schema_version=str(row["schema_version"]),
        )
    def require_workspace_object(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> None:
        row = self._conn.execute(
            "SELECT tenant_id, object_type FROM gov_objects WHERE object_id = ?",
            (workspace_object_id,),
        ).fetchone()
        if row is None:
            raise NotFoundGovernanceError(f"unknown workspace {workspace_object_id}")
        if str(row["tenant_id"]) != tenant_id:
            raise CrossTenantAccessError("workspace tenant mismatch")
        if str(row["object_type"]) != "Workspace":
            raise MalformedCommandError(
                f"object {workspace_object_id} is not a Workspace"
            )

    def _require_actor(self, actor_id: str, *, tenant_id: str) -> None:
        row = self._conn.execute(
            "SELECT tenant_id FROM gov_actors WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            raise NotFoundGovernanceError(f"unknown actor {actor_id}")
        if str(row["tenant_id"]) != tenant_id:
            raise CrossTenantAccessError("actor tenant mismatch")

    def _require_curate(
        self, actor_id: str, *, tenant_id: str, at: datetime
    ) -> None:
        self._require_actor(actor_id, tenant_id=tenant_id)
        if not self.actor_has_permission(
            tenant_id=tenant_id,
            actor_id=actor_id,
            permission=INTELLIGENCE_CURATE_PERMISSION,
            at=at,
        ):
            raise MissingAuthorityError(
                "actor lacks workspace.intelligence.curate authority"
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
        events = SqliteDomainEventRepository(self._conn)
        return events.append(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            correlation_id=workspace_object_id,
            causation_id=causation_id,
            created_at=at.isoformat(),
            actor_id=actor_id,
            payload_schema_version=M2_INTELLIGENCE_EVENT_SCHEMA_VERSION,
            occurred_at=at.isoformat(),
            subject_object_id=workspace_object_id,
        )

    # -- model revisions ------------------------------------------------------

    def save_model_revision(self, revision: WorkspaceModelRevision) -> None:
        self.require_workspace_object(
            revision.workspace_object_id, tenant_id=revision.tenant_id
        )
        self._require_curate(
            revision.created_by_actor_id,
            tenant_id=revision.tenant_id,
            at=revision.created_at,
        )
        if revision.approved_by_actor_id is not None:
            self._require_actor(
                revision.approved_by_actor_id, tenant_id=revision.tenant_id
            )
        self._insert_model_revision(revision)
        self._commit_write()

    def _insert_model_revision(self, revision: WorkspaceModelRevision) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_workspace_model_revisions(
                model_revision_id, tenant_id, workspace_object_id, revision, status,
                intent_seed_json, sections_json, based_on_revision_id,
                provenance_reference_ids_json, confidence_summary, created_at,
                created_by_actor_id, approved_by_actor_id, approved_at, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision.model_revision_id,
                revision.tenant_id,
                revision.workspace_object_id,
                revision.revision,
                revision.status.value,
                json.dumps(_intent_seed_to_dict(revision.intent_seed), sort_keys=True),
                json.dumps(
                    [_section_to_dict(section) for section in revision.sections]
                ),
                revision.based_on_revision_id,
                _json_list(revision.provenance_reference_ids),
                revision.confidence_summary,
                revision.created_at.isoformat(),
                revision.created_by_actor_id,
                revision.approved_by_actor_id,
                None if revision.approved_at is None else revision.approved_at.isoformat(),
                revision.schema_version,
            ),
        )

    def get_model_revision(
        self, model_revision_id: str
    ) -> WorkspaceModelRevision | None:
        row = self._conn.execute(
            "SELECT * FROM gov_workspace_model_revisions WHERE model_revision_id = ?",
            (model_revision_id,),
        ).fetchone()
        return None if row is None else self._model_revision_from_row(row)

    def list_model_revisions(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceModelRevision]:
        rows = self._conn.execute(
            """
            SELECT * FROM gov_workspace_model_revisions
            WHERE tenant_id = ? AND workspace_object_id = ?
            ORDER BY revision
            """,
            (tenant_id, workspace_object_id),
        ).fetchall()
        return [self._model_revision_from_row(row) for row in rows]

    def approve_model_revision(
        self,
        model_revision_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> WorkspaceModelRevision:
        current = self.get_model_revision(model_revision_id)
        if current is None:
            raise NotFoundGovernanceError(
                f"unknown model revision {model_revision_id}"
            )
        if current.tenant_id != tenant_id:
            raise CrossTenantAccessError("model revision tenant mismatch")
        if current.status is not ModelRevisionStatus.PROPOSED:
            raise MalformedCommandError("only proposed model revisions can be approved")
        self._require_curate(
            approved_by_actor_id, tenant_id=tenant_id, at=approved_at
        )
        previous = self._begin_write()
        try:
            self._apply_model_approval(
                current,
                approved_by_actor_id=approved_by_actor_id,
                approved_at=approved_at,
            )
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise
        updated = self.get_model_revision(model_revision_id)
        assert updated is not None
        return updated

    def _apply_model_approval(
        self,
        current: WorkspaceModelRevision,
        *,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> None:
        """Approve a proposed model and supersede prior approvals (caller owns txn)."""

        self._conn.execute(
            """
            UPDATE gov_workspace_model_revisions
            SET status = ?
            WHERE tenant_id = ? AND workspace_object_id = ?
              AND status = ? AND model_revision_id != ?
            """,
            (
                ModelRevisionStatus.SUPERSEDED.value,
                current.tenant_id,
                current.workspace_object_id,
                ModelRevisionStatus.APPROVED.value,
                current.model_revision_id,
            ),
        )
        self._conn.execute(
            """
            UPDATE gov_workspace_model_revisions
            SET status = ?, approved_by_actor_id = ?, approved_at = ?
            WHERE model_revision_id = ? AND status = ?
            """,
            (
                ModelRevisionStatus.APPROVED.value,
                approved_by_actor_id,
                approved_at.isoformat(),
                current.model_revision_id,
                ModelRevisionStatus.PROPOSED.value,
            ),
        )
        self._append_event(
            tenant_id=current.tenant_id,
            event_type=M2_EVENT_MODEL_APPROVED,
            actor_id=approved_by_actor_id,
            workspace_object_id=current.workspace_object_id,
            causation_id=current.model_revision_id,
            at=approved_at,
            payload={
                "model_revision_id": current.model_revision_id,
                "revision": current.revision,
            },
        )

    def _apply_source_trust_update(
        self,
        source: WorkspaceSource,
        *,
        to_trust: TrustClass,
        promotion_decision_id: str | None,
    ) -> WorkspaceSource:
        """Apply a trust promotion (caller owns txn / authority checks)."""

        assert_trust_promotion_allowed(
            from_trust=source.trust_class,
            to_trust=to_trust,
            decision_id=promotion_decision_id,
        )
        instruction_authority = to_trust is TrustClass.INSTRUCTION_AUTHORITY
        updated = WorkspaceSource(
            source_id=source.source_id,
            tenant_id=source.tenant_id,
            workspace_object_id=source.workspace_object_id,
            source_type=source.source_type,
            locator=source.locator,
            observed_revision=source.observed_revision,
            trust_class=to_trust,
            owner_actor_id=source.owner_actor_id,
            sensitivity=source.sensitivity,
            refresh_policy=source.refresh_policy,
            observed_at=source.observed_at,
            stale_status=source.stale_status,
            created_at=source.created_at,
            created_by_actor_id=source.created_by_actor_id,
            instruction_authority=instruction_authority,
            content_hash=source.content_hash,
            provenance_reference_id=source.provenance_reference_id,
            module_tags=source.module_tags,
            promotion_decision_id=promotion_decision_id
            if promotion_decision_id is not None
            else source.promotion_decision_id,
            schema_version=source.schema_version,
        )
        self._conn.execute(
            """
            UPDATE gov_workspace_sources
            SET trust_class = ?, instruction_authority = ?, promotion_decision_id = ?
            WHERE source_id = ?
            """,
            (
                updated.trust_class.value,
                1 if updated.instruction_authority else 0,
                updated.promotion_decision_id,
                source.source_id,
            ),
        )
        return updated

    def _apply_context_module_approval(
        self,
        module: ContextModule,
        *,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> ContextModule:
        """Approve a proposed context module (caller owns txn)."""

        approved = ContextModule(
            module_id=module.module_id,
            tenant_id=module.tenant_id,
            workspace_object_id=module.workspace_object_id,
            module_key=module.module_key,
            purpose_text=module.purpose_text,
            applicability_text=module.applicability_text,
            approval_status=ModuleApprovalStatus.APPROVED,
            freshness=module.freshness,
            created_at=module.created_at,
            created_by_actor_id=module.created_by_actor_id,
            revision=module.revision,
            item_ids=module.item_ids,
            source_ids=module.source_ids,
            approved_by_actor_id=approved_by_actor_id,
            approved_at=approved_at,
            schema_version=module.schema_version,
        )
        self._conn.execute(
            """
            UPDATE gov_context_modules
            SET approval_status = ?, approved_by_actor_id = ?, approved_at = ?
            WHERE module_id = ?
            """,
            (
                approved.approval_status.value,
                approved_by_actor_id,
                approved_at.isoformat(),
                module.module_id,
            ),
        )
        return approved

    # -- sources --------------------------------------------------------------

    def register_source(self, source: WorkspaceSource) -> None:
        self.require_workspace_object(
            source.workspace_object_id, tenant_id=source.tenant_id
        )
        self._require_actor(source.owner_actor_id, tenant_id=source.tenant_id)
        self._require_curate(
            source.created_by_actor_id,
            tenant_id=source.tenant_id,
            at=source.created_at,
        )
        existing = self.get_source_by_locator(
            tenant_id=source.tenant_id,
            workspace_object_id=source.workspace_object_id,
            locator=source.locator,
        )
        if existing is not None:
            raise IdempotencyConflictError(
                "a source with this natural key is already registered"
            )
        self._insert_source(source)
        self._commit_write()

    def _insert_source(self, source: WorkspaceSource) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_workspace_sources(
                source_id, tenant_id, workspace_object_id, source_type, locator,
                observed_revision, trust_class, owner_actor_id, sensitivity,
                refresh_policy, observed_at, stale_status, created_at,
                created_by_actor_id, instruction_authority, content_hash,
                provenance_reference_id, module_tags_json, promotion_decision_id,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.source_id,
                source.tenant_id,
                source.workspace_object_id,
                source.source_type.value,
                source.locator,
                source.observed_revision,
                source.trust_class.value,
                source.owner_actor_id,
                source.sensitivity,
                source.refresh_policy,
                source.observed_at.isoformat(),
                source.stale_status.value,
                source.created_at.isoformat(),
                source.created_by_actor_id,
                1 if source.instruction_authority else 0,
                source.content_hash,
                source.provenance_reference_id,
                _json_list(source.module_tags),
                source.promotion_decision_id,
                source.schema_version,
            ),
        )

    def get_source(self, source_id: str) -> WorkspaceSource | None:
        row = self._conn.execute(
            "SELECT * FROM gov_workspace_sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return None if row is None else self._source_from_row(row)

    def get_source_by_locator(
        self, *, tenant_id: str, workspace_object_id: str, locator: str
    ) -> WorkspaceSource | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_workspace_sources
            WHERE tenant_id = ? AND workspace_object_id = ? AND locator = ?
            """,
            (tenant_id, workspace_object_id, locator),
        ).fetchone()
        return None if row is None else self._source_from_row(row)

    def list_sources(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[WorkspaceSource]:
        rows = self._conn.execute(
            """
            SELECT * FROM gov_workspace_sources
            WHERE tenant_id = ? AND workspace_object_id = ?
            ORDER BY created_at, source_id
            """,
            (tenant_id, workspace_object_id),
        ).fetchall()
        return [self._source_from_row(row) for row in rows]

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
        source = self.get_source(source_id)
        if source is None:
            raise NotFoundGovernanceError(f"unknown source {source_id}")
        if source.tenant_id != tenant_id:
            raise CrossTenantAccessError("source tenant mismatch")
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)
        updated = self._apply_source_trust_update(
            source,
            to_trust=to_trust,
            promotion_decision_id=promotion_decision_id,
        )
        self._commit_write()
        return updated

    def mark_source_stale(
        self,
        source_id: str,
        *,
        tenant_id: str,
        dependent_module_ids: tuple[str, ...],
        actor_id: str,
        at: datetime,
    ) -> WorkspaceSource:
        """Mark a source and ONLY its listed dependent modules stale."""

        source = self.get_source(source_id)
        if source is None:
            raise NotFoundGovernanceError(f"unknown source {source_id}")
        if source.tenant_id != tenant_id:
            raise CrossTenantAccessError("source tenant mismatch")
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)
        modules = self._load_dependent_modules(
            dependent_module_ids,
            tenant_id=tenant_id,
            workspace_object_id=source.workspace_object_id,
        )
        previous = self._begin_write()
        try:
            self._mark_source_and_modules_stale_in_txn(
                source,
                modules=modules,
                actor_id=actor_id,
                at=at,
            )
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise
        refreshed = self.get_source(source_id)
        assert refreshed is not None
        return refreshed

    def apply_source_refreshes(
        self,
        workspace_object_id: str,
        *,
        tenant_id: str,
        refreshes: Sequence[tuple[str, str, str | None, tuple[str, ...]]],
        actor_id: str,
        at: datetime,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Update observed revisions and stale dependents in one transaction.

        Each refresh tuple is
        ``(source_id, new_observed_revision, content_hash, dependent_module_ids)``.
        """

        self.require_workspace_object(workspace_object_id, tenant_id=tenant_id)
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)
        prepared: list[
            tuple[WorkspaceSource, str, str | None, list[ContextModule]]
        ] = []
        for source_id, new_revision, content_hash, dependent_module_ids in refreshes:
            source = self.get_source(source_id)
            if source is None:
                raise NotFoundGovernanceError(f"unknown source {source_id}")
            if source.tenant_id != tenant_id:
                raise CrossTenantAccessError("source tenant mismatch")
            if source.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "source workspace does not match refresh target"
                )
            modules = self._load_dependent_modules(
                dependent_module_ids,
                tenant_id=tenant_id,
                workspace_object_id=workspace_object_id,
            )
            prepared.append((source, new_revision, content_hash, modules))

        refreshed_ids: list[str] = []
        staled_module_ids: list[str] = []
        previous = self._begin_write()
        try:
            for source, new_revision, content_hash, modules in prepared:
                self._conn.execute(
                    """
                    UPDATE gov_workspace_sources
                    SET observed_revision = ?,
                        content_hash = COALESCE(?, content_hash),
                        observed_at = ?
                    WHERE source_id = ?
                    """,
                    (
                        new_revision,
                        content_hash,
                        at.isoformat(),
                        source.source_id,
                    ),
                )
                self._mark_source_and_modules_stale_in_txn(
                    source,
                    modules=modules,
                    actor_id=actor_id,
                    at=at,
                )
                refreshed_ids.append(source.source_id)
                staled_module_ids.extend(module.module_id for module in modules)
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise
        # Preserve first-seen order while deduplicating module ids.
        seen: set[str] = set()
        unique_staled: list[str] = []
        for module_id in staled_module_ids:
            if module_id not in seen:
                seen.add(module_id)
                unique_staled.append(module_id)
        return tuple(refreshed_ids), tuple(unique_staled)

    def _load_dependent_modules(
        self,
        dependent_module_ids: tuple[str, ...],
        *,
        tenant_id: str,
        workspace_object_id: str,
    ) -> list[ContextModule]:
        modules: list[ContextModule] = []
        for module_id in dependent_module_ids:
            module = self.get_context_module(module_id)
            if module is None:
                raise NotFoundGovernanceError(f"unknown context module {module_id}")
            if module.tenant_id != tenant_id:
                raise CrossTenantAccessError("context module tenant mismatch")
            if module.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "dependent module must belong to the source workspace"
                )
            modules.append(module)
        return modules

    def _mark_source_and_modules_stale_in_txn(
        self,
        source: WorkspaceSource,
        *,
        modules: list[ContextModule],
        actor_id: str,
        at: datetime,
    ) -> None:
        """Mark source + listed modules stale and append events (caller owns txn)."""

        self._conn.execute(
            "UPDATE gov_workspace_sources SET stale_status = ? WHERE source_id = ?",
            (StaleStatus.STALE.value, source.source_id),
        )
        self._append_event(
            tenant_id=source.tenant_id,
            event_type=M2_EVENT_SOURCE_STALE,
            actor_id=actor_id,
            workspace_object_id=source.workspace_object_id,
            causation_id=source.source_id,
            at=at,
            payload={"source_id": source.source_id},
        )
        for module in modules:
            self._conn.execute(
                "UPDATE gov_context_modules SET freshness = ? WHERE module_id = ?",
                (StaleStatus.STALE.value, module.module_id),
            )
            self._append_event(
                tenant_id=source.tenant_id,
                event_type=M2_EVENT_CONTEXT_MODULE_STALE,
                actor_id=actor_id,
                workspace_object_id=source.workspace_object_id,
                causation_id=source.source_id,
                at=at,
                payload={
                    "module_id": module.module_id,
                    "source_id": source.source_id,
                },
            )

    # -- context items --------------------------------------------------------

    def save_context_item(self, item: ContextItem) -> None:
        self.require_workspace_object(
            item.workspace_object_id, tenant_id=item.tenant_id
        )
        self._require_curate(
            item.created_by_actor_id, tenant_id=item.tenant_id, at=item.created_at
        )
        if item.approved_by_actor_id is not None:
            self._require_actor(item.approved_by_actor_id, tenant_id=item.tenant_id)
        self._insert_context_item(item)
        self._commit_write()

    def _insert_context_item(self, item: ContextItem) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_context_items(
                item_id, tenant_id, workspace_object_id, item_type, statement,
                trust_class, validation_status, freshness, created_at,
                created_by_actor_id, source_reference_ids_json, confidence,
                applicability, conflicts_with_json, approved_by_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.item_id,
                item.tenant_id,
                item.workspace_object_id,
                item.item_type.value,
                item.statement,
                item.trust_class.value,
                item.validation_status.value,
                item.freshness.value,
                item.created_at.isoformat(),
                item.created_by_actor_id,
                _json_list(item.source_reference_ids),
                item.confidence,
                item.applicability,
                _json_list(item.conflicts_with_item_ids),
                item.approved_by_actor_id,
                item.schema_version,
            ),
        )

    def get_context_item(self, item_id: str) -> ContextItem | None:
        row = self._conn.execute(
            "SELECT * FROM gov_context_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return None if row is None else self._context_item_from_row(row)

    # -- context modules ------------------------------------------------------

    def save_context_module(self, module: ContextModule) -> None:
        self.require_workspace_object(
            module.workspace_object_id, tenant_id=module.tenant_id
        )
        self._require_curate(
            module.created_by_actor_id,
            tenant_id=module.tenant_id,
            at=module.created_at,
        )
        if module.approved_by_actor_id is not None:
            self._require_actor(
                module.approved_by_actor_id, tenant_id=module.tenant_id
            )
        self._insert_context_module(module)
        self._commit_write()

    def _insert_context_module(self, module: ContextModule) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_context_modules(
                module_id, tenant_id, workspace_object_id, module_key, purpose_text,
                applicability_text, approval_status, freshness, created_at,
                created_by_actor_id, revision, item_ids_json, source_ids_json,
                approved_by_actor_id, approved_at, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module.module_id,
                module.tenant_id,
                module.workspace_object_id,
                module.module_key,
                module.purpose_text,
                module.applicability_text,
                module.approval_status.value,
                module.freshness.value,
                module.created_at.isoformat(),
                module.created_by_actor_id,
                module.revision,
                _json_list(module.item_ids),
                _json_list(module.source_ids),
                module.approved_by_actor_id,
                None if module.approved_at is None else module.approved_at.isoformat(),
                module.schema_version,
            ),
        )

    def get_context_module(self, module_id: str) -> ContextModule | None:
        row = self._conn.execute(
            "SELECT * FROM gov_context_modules WHERE module_id = ?",
            (module_id,),
        ).fetchone()
        return None if row is None else self._context_module_from_row(row)

    def list_context_modules(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> list[ContextModule]:
        rows = self._conn.execute(
            """
            SELECT * FROM gov_context_modules
            WHERE tenant_id = ? AND workspace_object_id = ?
            ORDER BY module_key, revision
            """,
            (tenant_id, workspace_object_id),
        ).fetchall()
        return [self._context_module_from_row(row) for row in rows]

    def approve_context_module(
        self,
        module_id: str,
        *,
        tenant_id: str,
        approved_by_actor_id: str,
        approved_at: datetime,
    ) -> ContextModule:
        module = self.get_context_module(module_id)
        if module is None:
            raise NotFoundGovernanceError(f"unknown context module {module_id}")
        if module.tenant_id != tenant_id:
            raise CrossTenantAccessError("context module tenant mismatch")
        if module.approval_status is not ModuleApprovalStatus.PROPOSED:
            raise MalformedCommandError(
                "only proposed context modules can be approved"
            )
        self._require_curate(
            approved_by_actor_id, tenant_id=tenant_id, at=approved_at
        )
        approved = self._apply_context_module_approval(
            module,
            approved_by_actor_id=approved_by_actor_id,
            approved_at=approved_at,
        )
        self._commit_write()
        return approved

    # -- knowledge gaps -------------------------------------------------------

    def save_knowledge_gap(self, gap: KnowledgeGap) -> None:
        self.require_workspace_object(
            gap.workspace_object_id, tenant_id=gap.tenant_id
        )
        self._require_curate(
            gap.created_by_actor_id, tenant_id=gap.tenant_id, at=gap.created_at
        )
        if gap.owner_actor_id is not None:
            self._require_actor(gap.owner_actor_id, tenant_id=gap.tenant_id)
        self._insert_knowledge_gap(gap)
        self._commit_write()

    def _insert_knowledge_gap(self, gap: KnowledgeGap) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_knowledge_gaps(
                gap_id, tenant_id, workspace_object_id, question,
                affected_sections_json, impact_text, risk_if_unresolved_text, status,
                created_at, created_by_actor_id, owner_actor_id,
                resolution_reference_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gap.gap_id,
                gap.tenant_id,
                gap.workspace_object_id,
                gap.question,
                _json_list(gap.affected_sections),
                gap.impact_text,
                gap.risk_if_unresolved_text,
                gap.status.value,
                gap.created_at.isoformat(),
                gap.created_by_actor_id,
                gap.owner_actor_id,
                gap.resolution_reference_id,
                gap.schema_version,
            ),
        )

    def get_knowledge_gap(self, gap_id: str) -> KnowledgeGap | None:
        row = self._conn.execute(
            "SELECT * FROM gov_knowledge_gaps WHERE gap_id = ?",
            (gap_id,),
        ).fetchone()
        return None if row is None else self._knowledge_gap_from_row(row)

    def list_knowledge_gaps(
        self, workspace_object_id: str, *, tenant_id: str, status: GapStatus | None = None
    ) -> list[KnowledgeGap]:
        if status is None:
            rows = self._conn.execute(
                """
                SELECT * FROM gov_knowledge_gaps
                WHERE tenant_id = ? AND workspace_object_id = ?
                ORDER BY created_at, gap_id
                """,
                (tenant_id, workspace_object_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM gov_knowledge_gaps
                WHERE tenant_id = ? AND workspace_object_id = ? AND status = ?
                ORDER BY created_at, gap_id
                """,
                (tenant_id, workspace_object_id, status.value),
            ).fetchall()
        return [self._knowledge_gap_from_row(row) for row in rows]

    def resolve_knowledge_gap(
        self,
        gap_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> KnowledgeGap:
        gap = self.get_knowledge_gap(gap_id)
        if gap is None:
            raise NotFoundGovernanceError(f"unknown knowledge gap {gap_id}")
        if gap.tenant_id != tenant_id:
            raise CrossTenantAccessError("knowledge gap tenant mismatch")
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)
        resolved = KnowledgeGap(
            gap_id=gap.gap_id,
            tenant_id=gap.tenant_id,
            workspace_object_id=gap.workspace_object_id,
            question=gap.question,
            affected_sections=gap.affected_sections,
            impact_text=gap.impact_text,
            risk_if_unresolved_text=gap.risk_if_unresolved_text,
            status=GapStatus.RESOLVED,
            created_at=gap.created_at,
            created_by_actor_id=gap.created_by_actor_id,
            owner_actor_id=gap.owner_actor_id,
            resolution_reference_id=resolution_reference_id,
            schema_version=gap.schema_version,
        )
        self._conn.execute(
            """
            UPDATE gov_knowledge_gaps
            SET status = ?, resolution_reference_id = ?
            WHERE gap_id = ?
            """,
            (resolved.status.value, resolution_reference_id, gap_id),
        )
        self._commit_write()
        return resolved

    # -- contradictions -------------------------------------------------------

    def save_contradiction(self, contradiction: Contradiction) -> None:
        self.require_workspace_object(
            contradiction.workspace_object_id, tenant_id=contradiction.tenant_id
        )
        self._require_curate(
            contradiction.created_by_actor_id,
            tenant_id=contradiction.tenant_id,
            at=contradiction.created_at,
        )
        self._insert_contradiction(contradiction)
        self._commit_write()

    def _insert_contradiction(self, contradiction: Contradiction) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_contradictions(
                contradiction_id, tenant_id, workspace_object_id,
                claim_reference_ids_json, description, impact_text, status,
                created_at, created_by_actor_id, resolution_reference_id,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contradiction.contradiction_id,
                contradiction.tenant_id,
                contradiction.workspace_object_id,
                _json_list(contradiction.claim_reference_ids),
                contradiction.description,
                contradiction.impact_text,
                contradiction.status.value,
                contradiction.created_at.isoformat(),
                contradiction.created_by_actor_id,
                contradiction.resolution_reference_id,
                contradiction.schema_version,
            ),
        )

    def get_contradiction(self, contradiction_id: str) -> Contradiction | None:
        row = self._conn.execute(
            "SELECT * FROM gov_contradictions WHERE contradiction_id = ?",
            (contradiction_id,),
        ).fetchone()
        return None if row is None else self._contradiction_from_row(row)

    def resolve_contradiction(
        self,
        contradiction_id: str,
        *,
        tenant_id: str,
        resolution_reference_id: str,
        actor_id: str,
        at: datetime,
    ) -> Contradiction:
        contradiction = self.get_contradiction(contradiction_id)
        if contradiction is None:
            raise NotFoundGovernanceError(
                f"unknown contradiction {contradiction_id}"
            )
        if contradiction.tenant_id != tenant_id:
            raise CrossTenantAccessError("contradiction tenant mismatch")
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)
        resolved = Contradiction(
            contradiction_id=contradiction.contradiction_id,
            tenant_id=contradiction.tenant_id,
            workspace_object_id=contradiction.workspace_object_id,
            claim_reference_ids=contradiction.claim_reference_ids,
            description=contradiction.description,
            impact_text=contradiction.impact_text,
            status=ContradictionStatus.RESOLVED,
            created_at=contradiction.created_at,
            created_by_actor_id=contradiction.created_by_actor_id,
            resolution_reference_id=resolution_reference_id,
            schema_version=contradiction.schema_version,
        )
        self._conn.execute(
            """
            UPDATE gov_contradictions
            SET status = ?, resolution_reference_id = ?
            WHERE contradiction_id = ?
            """,
            (resolved.status.value, resolution_reference_id, contradiction_id),
        )
        self._commit_write()
        return resolved

    # -- decisions ------------------------------------------------------------

    def save_workspace_decision(self, decision: WorkspaceDecision) -> None:
        self.require_workspace_object(
            decision.workspace_object_id, tenant_id=decision.tenant_id
        )
        self._require_curate(
            decision.authorized_actor_id,
            tenant_id=decision.tenant_id,
            at=decision.decided_at,
        )
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_workspace_decisions(
                decision_id, tenant_id, workspace_object_id, subject_revision_id,
                outcome, rationale, authorized_actor_id, decided_at,
                signed_source_reference_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.tenant_id,
                decision.workspace_object_id,
                decision.subject_revision_id,
                decision.outcome.value,
                decision.rationale,
                decision.authorized_actor_id,
                decision.decided_at.isoformat(),
                decision.signed_source_reference_id,
                decision.schema_version,
            ),
        )
        self._commit_write()

    def get_workspace_decision(self, decision_id: str) -> WorkspaceDecision | None:
        row = self._conn.execute(
            "SELECT * FROM gov_workspace_decisions WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        return None if row is None else self._decision_from_row(row)

    # -- readiness ------------------------------------------------------------

    def save_readiness_assessment(
        self, assessment: WorkspaceReadinessAssessment
    ) -> None:
        self.require_workspace_object(
            assessment.workspace_object_id, tenant_id=assessment.tenant_id
        )
        self._require_curate(
            assessment.assessed_by_actor_id,
            tenant_id=assessment.tenant_id,
            at=assessment.assessed_at,
        )
        self._insert_readiness(assessment)
        self._commit_write()

    def _insert_readiness(self, assessment: WorkspaceReadinessAssessment) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_workspace_readiness_assessments(
                assessment_id, tenant_id, workspace_object_id, model_revision_id,
                level, dimensions_checked_json, open_gap_ids_json, policy_basis,
                evaluator_summary, assessed_at, assessed_by_actor_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.assessment_id,
                assessment.tenant_id,
                assessment.workspace_object_id,
                assessment.model_revision_id,
                assessment.level.value,
                _json_list(assessment.dimensions_checked),
                _json_list(assessment.open_gap_ids),
                assessment.policy_basis,
                assessment.evaluator_summary,
                assessment.assessed_at.isoformat(),
                assessment.assessed_by_actor_id,
                assessment.schema_version,
            ),
        )

    def get_readiness_assessment(
        self, assessment_id: str
    ) -> WorkspaceReadinessAssessment | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_workspace_readiness_assessments
            WHERE assessment_id = ?
            """,
            (assessment_id,),
        ).fetchone()
        return None if row is None else self._readiness_from_row(row)

    def get_latest_readiness(
        self, workspace_object_id: str, *, tenant_id: str
    ) -> WorkspaceReadinessAssessment | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_workspace_readiness_assessments
            WHERE tenant_id = ? AND workspace_object_id = ?
            ORDER BY assessed_at DESC, assessment_id DESC
            LIMIT 1
            """,
            (tenant_id, workspace_object_id),
        ).fetchone()
        return None if row is None else self._readiness_from_row(row)

    # -- onboarding -----------------------------------------------------------

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
    ]:
        """Persist a proposed intelligence set in one governed transaction."""

        tenant_id = model.tenant_id
        workspace_object_id = model.workspace_object_id
        self.require_workspace_object(workspace_object_id, tenant_id=tenant_id)
        self._require_curate(actor_id, tenant_id=tenant_id, at=at)

        if model.status is not ModelRevisionStatus.PROPOSED:
            raise MalformedCommandError("onboarding requires a proposed model revision")
        if readiness.model_revision_id != model.model_revision_id:
            raise MalformedCommandError(
                "readiness must reference the proposed model revision"
            )

        for record in (
            *sources,
            *modules,
            *items,
            *gaps,
            readiness,
        ):
            if record.tenant_id != tenant_id:
                raise CrossTenantAccessError("onboarding records must share the tenant")
            if record.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "onboarding records must share the workspace"
                )

        for source in sources:
            if (
                source.instruction_authority
                or source.trust_class is TrustClass.INSTRUCTION_AUTHORITY
            ):
                raise MalformedCommandError(
                    "onboarding cannot register instruction-authority sources "
                    "without explicit human promotion"
                )
        for item in items:
            if item.trust_class is TrustClass.INSTRUCTION_AUTHORITY and not (
                item.item_type is ContextItemType.APPROVED_INSTRUCTION
                and item.approved_by_actor_id is not None
            ):
                raise MalformedCommandError(
                    "onboarding cannot introduce instruction authority without approval"
                )
        for gap in gaps:
            if gap.status is not GapStatus.OPEN:
                raise MalformedCommandError("onboarding gaps must start open")

        command_id = generate_uuidv7()
        event_types: list[str] = []
        previous = self._begin_write()
        try:
            self._insert_model_revision(model)
            for source in sources:
                self._require_actor(source.owner_actor_id, tenant_id=tenant_id)
                existing = self.get_source_by_locator(
                    tenant_id=tenant_id,
                    workspace_object_id=workspace_object_id,
                    locator=source.locator,
                )
                if existing is not None:
                    raise IdempotencyConflictError(
                        "a source with this natural key is already registered"
                    )
                self._insert_source(source)
            for item in items:
                if item.approved_by_actor_id is not None:
                    self._require_actor(
                        item.approved_by_actor_id, tenant_id=tenant_id
                    )
                self._insert_context_item(item)
            for module in modules:
                if module.approved_by_actor_id is not None:
                    self._require_actor(
                        module.approved_by_actor_id, tenant_id=tenant_id
                    )
                self._insert_context_module(module)
            for gap in gaps:
                if gap.owner_actor_id is not None:
                    self._require_actor(gap.owner_actor_id, tenant_id=tenant_id)
                self._insert_knowledge_gap(gap)
            self._insert_readiness(readiness)

            self._append_event(
                tenant_id=tenant_id,
                event_type=M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED,
                actor_id=actor_id,
                workspace_object_id=workspace_object_id,
                causation_id=command_id,
                at=at,
                payload={"model_revision_id": model.model_revision_id},
            )
            event_types.append(M2_EVENT_INTELLIGENCE_ONBOARDING_REQUESTED)
            self._append_event(
                tenant_id=tenant_id,
                event_type=M2_EVENT_MODEL_PROPOSED,
                actor_id=actor_id,
                workspace_object_id=workspace_object_id,
                causation_id=command_id,
                at=at,
                payload={
                    "model_revision_id": model.model_revision_id,
                    "revision": model.revision,
                },
            )
            event_types.append(M2_EVENT_MODEL_PROPOSED)
            for source in sources:
                self._append_event(
                    tenant_id=tenant_id,
                    event_type=M2_EVENT_SOURCE_REGISTERED,
                    actor_id=actor_id,
                    workspace_object_id=workspace_object_id,
                    causation_id=command_id,
                    at=at,
                    payload={"source_id": source.source_id, "locator": source.locator},
                )
                event_types.append(M2_EVENT_SOURCE_REGISTERED)
            for gap in gaps:
                self._append_event(
                    tenant_id=tenant_id,
                    event_type=M2_EVENT_KNOWLEDGE_GAP_CREATED,
                    actor_id=actor_id,
                    workspace_object_id=workspace_object_id,
                    causation_id=command_id,
                    at=at,
                    payload={"gap_id": gap.gap_id},
                )
                event_types.append(M2_EVENT_KNOWLEDGE_GAP_CREATED)
            self._append_event(
                tenant_id=tenant_id,
                event_type=M2_EVENT_READINESS_ASSESSED,
                actor_id=actor_id,
                workspace_object_id=workspace_object_id,
                causation_id=command_id,
                at=at,
                payload={
                    "assessment_id": readiness.assessment_id,
                    "level": readiness.level.value,
                },
            )
            event_types.append(M2_EVENT_READINESS_ASSESSED)
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise

        return (
            model,
            tuple(sources),
            tuple(modules),
            tuple(items),
            tuple(gaps),
            readiness,
            tuple(event_types),
        )

    def activate_curation(
        self,
        proposal: WorkspaceCurationProposal,
    ) -> tuple[
        WorkspaceModelRevision,
        tuple[ContextModule, ...],
        tuple[WorkspaceSource, ...],
        WorkspaceReadinessAssessment,
        tuple[str, ...],
    ]:
        """Apply trust promotions, approvals, and readiness in one transaction.

        Application validation and curate permission must already have passed.
        """

        tenant_id = proposal.tenant_id
        workspace_object_id = proposal.workspace_object_id
        self.require_workspace_object(workspace_object_id, tenant_id=tenant_id)
        self._require_curate(proposal.actor_id, tenant_id=tenant_id, at=proposal.at)

        model = self.get_model_revision(proposal.model_revision_id)
        if model is None:
            raise NotFoundGovernanceError(
                f"unknown model revision {proposal.model_revision_id}"
            )
        if model.tenant_id != tenant_id:
            raise CrossTenantAccessError("model revision tenant mismatch")
        if model.workspace_object_id != workspace_object_id:
            raise MalformedCommandError(
                "model revision workspace does not match curation proposal"
            )
        if model.status is not ModelRevisionStatus.PROPOSED:
            raise MalformedCommandError(
                "only proposed model revisions can be activated"
            )

        sources_to_promote: list[tuple[WorkspaceSource, TrustClass, str | None]] = []
        for promotion in proposal.trust_promotions:
            source = self.get_source(promotion.source_id)
            if source is None:
                raise NotFoundGovernanceError(f"unknown source {promotion.source_id}")
            if source.tenant_id != tenant_id:
                raise CrossTenantAccessError("source tenant mismatch")
            if source.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "source workspace does not match curation proposal"
                )
            sources_to_promote.append(
                (source, promotion.to_trust, promotion.decision_id)
            )

        modules_to_approve: list[ContextModule] = []
        for module_id in proposal.module_ids_to_approve:
            module = self.get_context_module(module_id)
            if module is None:
                raise NotFoundGovernanceError(f"unknown context module {module_id}")
            if module.tenant_id != tenant_id:
                raise CrossTenantAccessError("context module tenant mismatch")
            if module.workspace_object_id != workspace_object_id:
                raise MalformedCommandError(
                    "context module workspace does not match curation proposal"
                )
            if module.approval_status is not ModuleApprovalStatus.PROPOSED:
                raise MalformedCommandError(
                    "only proposed context modules can be approved"
                )
            modules_to_approve.append(module)

        assessment_id = proposal.assessment_id or generate_uuidv7()
        readiness = WorkspaceReadinessAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            workspace_object_id=workspace_object_id,
            model_revision_id=proposal.model_revision_id,
            level=proposal.claimed_readiness_level,
            dimensions_checked=proposal.dimensions_checked,
            open_gap_ids=proposal.open_gap_ids,
            policy_basis=proposal.policy_basis,
            evaluator_summary=proposal.evaluator_summary,
            assessed_at=proposal.at,
            assessed_by_actor_id=proposal.actor_id,
        )

        event_types: list[str] = []
        previous = self._begin_write()
        try:
            promoted_sources: list[WorkspaceSource] = []
            for source, to_trust, decision_id in sources_to_promote:
                promoted_sources.append(
                    self._apply_source_trust_update(
                        source,
                        to_trust=to_trust,
                        promotion_decision_id=decision_id,
                    )
                )

            self._apply_model_approval(
                model,
                approved_by_actor_id=proposal.actor_id,
                approved_at=proposal.at,
            )
            event_types.append(M2_EVENT_MODEL_APPROVED)

            approved_modules: list[ContextModule] = []
            for module in modules_to_approve:
                approved_modules.append(
                    self._apply_context_module_approval(
                        module,
                        approved_by_actor_id=proposal.actor_id,
                        approved_at=proposal.at,
                    )
                )

            actual_open = {
                gap.gap_id
                for gap in self.list_knowledge_gaps(
                    workspace_object_id,
                    tenant_id=tenant_id,
                    status=GapStatus.OPEN,
                )
            }
            if set(proposal.open_gap_ids) != actual_open:
                raise MalformedCommandError(
                    "open_gap_ids must exactly match open knowledge gaps"
                )

            self._insert_readiness(readiness)
            self._append_event(
                tenant_id=tenant_id,
                event_type=M2_EVENT_READINESS_ASSESSED,
                actor_id=proposal.actor_id,
                workspace_object_id=workspace_object_id,
                causation_id=proposal.model_revision_id,
                at=proposal.at,
                payload={
                    "assessment_id": readiness.assessment_id,
                    "level": readiness.level.value,
                    "model_revision_id": proposal.model_revision_id,
                },
            )
            event_types.append(M2_EVENT_READINESS_ASSESSED)
            self._commit_txn(previous)
        except Exception:
            self._rollback_txn(previous)
            raise

        approved_model = self.get_model_revision(proposal.model_revision_id)
        assert approved_model is not None
        return (
            approved_model,
            tuple(approved_modules),
            tuple(promoted_sources),
            readiness,
            tuple(event_types),
        )

    # -- row reconstruction ---------------------------------------------------

    @staticmethod
    def _model_revision_from_row(row: sqlite3.Row) -> WorkspaceModelRevision:
        status = ModelRevisionStatus(str(row["status"]))
        approved_by = row["approved_by_actor_id"]
        approved_at = row["approved_at"]
        based_on = row["based_on_revision_id"]
        # Approval provenance is retained in storage but the domain contract only
        # carries it on records still in the approved state.
        is_approved = status is ModelRevisionStatus.APPROVED
        return WorkspaceModelRevision(
            model_revision_id=str(row["model_revision_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            revision=int(row["revision"]),
            status=status,
            intent_seed=_intent_seed_from_dict(
                json.loads(str(row["intent_seed_json"]))
            ),
            sections=tuple(
                _section_from_dict(item)
                for item in json.loads(str(row["sections_json"]))
            ),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            based_on_revision_id=None if based_on is None else str(based_on),
            provenance_reference_ids=_read_list(row["provenance_reference_ids_json"]),
            confidence_summary=str(row["confidence_summary"]),
            approved_by_actor_id=(
                str(approved_by) if is_approved and approved_by is not None else None
            ),
            approved_at=(
                datetime.fromisoformat(str(approved_at))
                if is_approved and approved_at is not None
                else None
            ),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> WorkspaceSource:
        content_hash = row["content_hash"]
        provenance = row["provenance_reference_id"]
        keys = row.keys()
        promotion_decision = (
            row["promotion_decision_id"]
            if "promotion_decision_id" in keys
            else None
        )
        return WorkspaceSource(
            source_id=str(row["source_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            source_type=SourceType(str(row["source_type"])),
            locator=str(row["locator"]),
            observed_revision=str(row["observed_revision"]),
            trust_class=TrustClass(str(row["trust_class"])),
            owner_actor_id=str(row["owner_actor_id"]),
            sensitivity=str(row["sensitivity"]),
            refresh_policy=str(row["refresh_policy"]),
            observed_at=datetime.fromisoformat(str(row["observed_at"])),
            stale_status=StaleStatus(str(row["stale_status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            instruction_authority=bool(row["instruction_authority"]),
            content_hash=None if content_hash is None else str(content_hash),
            provenance_reference_id=None if provenance is None else str(provenance),
            module_tags=_read_list(row["module_tags_json"]),
            promotion_decision_id=(
                None if promotion_decision is None else str(promotion_decision)
            ),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _context_item_from_row(row: sqlite3.Row) -> ContextItem:
        confidence = row["confidence"]
        approved_by = row["approved_by_actor_id"]
        return ContextItem(
            item_id=str(row["item_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            item_type=ContextItemType(str(row["item_type"])),
            statement=str(row["statement"]),
            trust_class=TrustClass(str(row["trust_class"])),
            validation_status=ValidationStatus(str(row["validation_status"])),
            freshness=StaleStatus(str(row["freshness"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            source_reference_ids=_read_list(row["source_reference_ids_json"]),
            confidence=None if confidence is None else float(confidence),
            applicability=str(row["applicability"]),
            conflicts_with_item_ids=_read_list(row["conflicts_with_json"]),
            approved_by_actor_id=None if approved_by is None else str(approved_by),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _context_module_from_row(row: sqlite3.Row) -> ContextModule:
        approved_by = row["approved_by_actor_id"]
        approved_at = row["approved_at"]
        return ContextModule(
            module_id=str(row["module_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            module_key=str(row["module_key"]),
            purpose_text=str(row["purpose_text"]),
            applicability_text=str(row["applicability_text"]),
            approval_status=ModuleApprovalStatus(str(row["approval_status"])),
            freshness=StaleStatus(str(row["freshness"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            revision=int(row["revision"]),
            item_ids=_read_list(row["item_ids_json"]),
            source_ids=_read_list(row["source_ids_json"]),
            approved_by_actor_id=None if approved_by is None else str(approved_by),
            approved_at=(
                None if approved_at is None else datetime.fromisoformat(str(approved_at))
            ),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _knowledge_gap_from_row(row: sqlite3.Row) -> KnowledgeGap:
        owner = row["owner_actor_id"]
        resolution = row["resolution_reference_id"]
        return KnowledgeGap(
            gap_id=str(row["gap_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            question=str(row["question"]),
            affected_sections=_read_list(row["affected_sections_json"]),
            impact_text=str(row["impact_text"]),
            risk_if_unresolved_text=str(row["risk_if_unresolved_text"]),
            status=GapStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            owner_actor_id=None if owner is None else str(owner),
            resolution_reference_id=None if resolution is None else str(resolution),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _contradiction_from_row(row: sqlite3.Row) -> Contradiction:
        resolution = row["resolution_reference_id"]
        return Contradiction(
            contradiction_id=str(row["contradiction_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            claim_reference_ids=_read_list(row["claim_reference_ids_json"]),
            description=str(row["description"]),
            impact_text=str(row["impact_text"]),
            status=ContradictionStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            resolution_reference_id=None if resolution is None else str(resolution),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _decision_from_row(row: sqlite3.Row) -> WorkspaceDecision:
        signed = row["signed_source_reference_id"]
        return WorkspaceDecision(
            decision_id=str(row["decision_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            subject_revision_id=str(row["subject_revision_id"]),
            outcome=DecisionOutcome(str(row["outcome"])),
            rationale=str(row["rationale"]),
            authorized_actor_id=str(row["authorized_actor_id"]),
            decided_at=datetime.fromisoformat(str(row["decided_at"])),
            signed_source_reference_id=None if signed is None else str(signed),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _readiness_from_row(row: sqlite3.Row) -> WorkspaceReadinessAssessment:
        return WorkspaceReadinessAssessment(
            assessment_id=str(row["assessment_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            model_revision_id=str(row["model_revision_id"]),
            level=ReadinessLevel(str(row["level"])),
            dimensions_checked=_read_list(row["dimensions_checked_json"]),
            open_gap_ids=_read_list(row["open_gap_ids_json"]),
            policy_basis=str(row["policy_basis"]),
            evaluator_summary=str(row["evaluator_summary"]),
            assessed_at=datetime.fromisoformat(str(row["assessed_at"])),
            assessed_by_actor_id=str(row["assessed_by_actor_id"]),
            schema_version=str(row["schema_version"]),
        )


def _intent_seed_to_dict(seed: IntentSeed) -> dict[str, str]:
    return {
        "purpose_text": seed.purpose_text,
        "primary_users_text": seed.primary_users_text,
        "important_risks_text": seed.important_risks_text,
        "non_goals_text": seed.non_goals_text,
        "decisions_not_automatic_text": seed.decisions_not_automatic_text,
    }


def _intent_seed_from_dict(data: dict[str, str]) -> IntentSeed:
    return IntentSeed(
        purpose_text=str(data["purpose_text"]),
        primary_users_text=str(data["primary_users_text"]),
        important_risks_text=str(data["important_risks_text"]),
        non_goals_text=str(data["non_goals_text"]),
        decisions_not_automatic_text=str(data["decisions_not_automatic_text"]),
    )


def _section_to_dict(section: ModelSectionState) -> dict[str, object]:
    return {
        "section_key": section.section_key,
        "certainty": section.certainty.value,
        "summary_hash": section.summary_hash,
    }


def _section_from_dict(data: dict[str, object]) -> ModelSectionState:
    summary_hash = data.get("summary_hash")
    return ModelSectionState(
        section_key=str(data["section_key"]),
        certainty=SectionCertainty(str(data["certainty"])),
        summary_hash=None if summary_hash is None else str(summary_hash),
    )
