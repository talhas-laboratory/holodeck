"""Persisted actors, roles, assignments, grants, and approvals."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.assignments import (
    RoleAssignment,
    assignment_is_active,
)
from holodeck_governance.domain.authority.grants import (
    DelegatedGrant,
    GrantExpiredError,
    GrantRevokedError,
    GrantWrongRevisionError,
    RevocationDecision,
    assert_grant_authorizes,
)
from holodeck_governance.domain.authority.roles import RoleProfile
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.errors import (
    MissingAuthorityError,
    NotFoundGovernanceError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.review import ApprovalRecord
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


def _insert_immutable(conn: sqlite3.Connection, sql: str, params: tuple) -> None:
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        raise RevisionImmutableError(
            "authority record already exists and cannot be overwritten"
        ) from exc


class SqliteAuthorityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        migrate_governance(conn)

    def save_actor(self, actor: Actor) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_actors(
                actor_id, tenant_id, kind, display_name, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor.actor_id,
                actor.tenant_id,
                actor.kind.value,
                actor.display_name,
                actor.schema_version,
                actor.created_at.isoformat(),
                actor.created_by_actor_id,
            ),
        )

    def get_actor(self, actor_id: str) -> Actor | None:
        row = self._conn.execute(
            "SELECT * FROM gov_actors WHERE actor_id = ?", (actor_id,)
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

    def require_actor(self, actor_id: str) -> Actor:
        actor = self.get_actor(actor_id)
        if actor is None:
            raise NotFoundGovernanceError(f"unknown actor {actor_id}")
        return actor

    def save_role_profile(self, role: RoleProfile) -> None:
        revisions = SqliteRevisionRepository(self._conn)
        if revisions.get_object(role.role_object_id) is None:
            revisions.register_object(
                GovernanceObject(
                    object_id=role.role_object_id,
                    tenant_id=role.tenant_id,
                    object_type="RoleProfile",
                    created_at=role.created_at,
                    created_by_actor_id=role.created_by_actor_id,
                )
            )
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_role_profiles(
                role_object_id, revision, tenant_id, name, permissions_json,
                jurisdiction_json, schema_version, created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                role.role_object_id,
                role.revision,
                role.tenant_id,
                role.name,
                json.dumps(list(role.permissions)),
                json.dumps(dict(role.jurisdiction), sort_keys=True),
                role.schema_version,
                role.created_at.isoformat(),
                role.created_by_actor_id,
            ),
        )

    def save_assignment(self, assignment: RoleAssignment) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_role_assignments(
                assignment_id, tenant_id, actor_id, role_object_id, role_revision,
                workspace_object_id, jurisdiction_key, jurisdiction_value,
                effective_from, effective_until, created_at, created_by_actor_id,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment.assignment_id,
                assignment.tenant_id,
                assignment.actor_id,
                assignment.role_object_id,
                assignment.role_revision,
                assignment.workspace_object_id,
                assignment.jurisdiction_key,
                assignment.jurisdiction_value,
                assignment.effective_from.isoformat(),
                assignment.effective_until.isoformat()
                if assignment.effective_until
                else None,
                assignment.created_at.isoformat(),
                assignment.created_by_actor_id,
                assignment.schema_version,
            ),
        )

    def save_grant(self, grant: DelegatedGrant) -> None:
        if grant.issuance_basis_id is None:
            raise MissingAuthorityError("grant issuance basis is required")
        self._assert_grant_issuance_authorized(grant)
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_delegated_grants(
                grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
                subject_object_id, subject_revision, effective_from, expires_at,
                created_at, created_by_actor_id, issuance_basis_kind, issuance_basis_id,
                redelegatable, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grant.grant_id,
                grant.tenant_id,
                grant.delegator_actor_id,
                grant.recipient_actor_id,
                grant.permission,
                grant.subject_object_id,
                grant.subject_revision,
                grant.effective_from.isoformat(),
                grant.expires_at.isoformat(),
                grant.created_at.isoformat(),
                grant.created_by_actor_id,
                grant.issuance_basis_kind,
                grant.issuance_basis_id,
                1 if grant.redelegatable else 0,
                grant.schema_version,
            ),
        )

    def save_revocation(self, revocation: RevocationDecision) -> None:
        if revocation.issuance_basis_id is None:
            raise MissingAuthorityError("revocation issuance basis is required")
        self._assert_revocation_issuance_authorized(revocation)
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_revocation_decisions(
                revocation_id, tenant_id, grant_id, created_at, created_by_actor_id,
                rationale, issuance_basis_kind, issuance_basis_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revocation.revocation_id,
                revocation.tenant_id,
                revocation.grant_id,
                revocation.created_at.isoformat(),
                revocation.created_by_actor_id,
                revocation.rationale,
                revocation.issuance_basis_kind,
                revocation.issuance_basis_id,
                revocation.schema_version,
            ),
        )

    def _active_delegation_assignment(
        self, *, assignment_id: str, actor_id: str, tenant_id: str,
        permission: str, at: datetime
    ) -> bool:
        row = self._conn.execute(
            """
            SELECT a.*, p.permissions_json FROM gov_role_assignments a
            JOIN gov_role_profiles p ON p.role_object_id = a.role_object_id
              AND p.revision = a.role_revision
            WHERE a.assignment_id = ? AND a.tenant_id = ? AND a.actor_id = ?
            """, (assignment_id, tenant_id, actor_id)
        ).fetchone()
        if row is None:
            return False
        assignment = RoleAssignment(
            assignment_id=str(row["assignment_id"]), tenant_id=str(row["tenant_id"]),
            actor_id=str(row["actor_id"]), role_object_id=str(row["role_object_id"]),
            role_revision=int(row["role_revision"]), workspace_object_id=row["workspace_object_id"],
            jurisdiction_key=str(row["jurisdiction_key"]), jurisdiction_value=str(row["jurisdiction_value"]),
            effective_from=datetime.fromisoformat(str(row["effective_from"])),
            effective_until=(datetime.fromisoformat(str(row["effective_until"])) if row["effective_until"] else None),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            created_by_actor_id=str(row["created_by_actor_id"]), schema_version=str(row["schema_version"]),
        )
        if not assignment_is_active(assignment, at=at):
            return False
        permissions = set(json.loads(str(row["permissions_json"])))
        return permission in permissions or permission.rsplit(":", 1)[0] + ":*" in permissions or "*" in permissions

    def _assert_grant_issuance_authorized(self, grant: DelegatedGrant) -> None:
        if grant.issuance_basis_kind == "role_assignment":
            ok = self._active_delegation_assignment(
                assignment_id=str(grant.issuance_basis_id), actor_id=grant.delegator_actor_id,
                tenant_id=grant.tenant_id, permission=f"delegate:{grant.permission}", at=grant.created_at,
            )
        else:
            row = self._conn.execute(
                "SELECT * FROM gov_delegated_grants WHERE grant_id = ? AND tenant_id = ?",
                (grant.issuance_basis_id, grant.tenant_id),
            ).fetchone()
            ok = bool(row) and bool(row["redelegatable"]) and str(row["recipient_actor_id"]) == grant.delegator_actor_id and str(row["permission"]) == grant.permission and str(row["subject_object_id"]) == grant.subject_object_id and int(row["subject_revision"]) == grant.subject_revision
        if not ok:
            raise MissingAuthorityError("delegator lacks an active issuance basis")

    def _assert_revocation_issuance_authorized(self, revocation: RevocationDecision) -> None:
        grant = self._conn.execute(
            "SELECT * FROM gov_delegated_grants WHERE grant_id = ? AND tenant_id = ?",
            (revocation.grant_id, revocation.tenant_id),
        ).fetchone()
        if grant is None:
            raise NotFoundGovernanceError("grant not found in revocation tenant")
        if revocation.issuance_basis_kind == "delegator":
            ok = str(revocation.issuance_basis_id) == revocation.grant_id and str(grant["delegator_actor_id"]) == revocation.created_by_actor_id
        else:
            ok = self._active_delegation_assignment(
                assignment_id=str(revocation.issuance_basis_id), actor_id=revocation.created_by_actor_id,
                tenant_id=revocation.tenant_id, permission=f"revoke:{grant['permission']}", at=revocation.created_at,
            )
        if not ok:
            raise MissingAuthorityError("revoker lacks an active issuance basis")

    def save_approval(self, approval: ApprovalRecord) -> None:
        revisions = SqliteRevisionRepository(self._conn)
        if revisions.get_object(approval.object_id) is None:
            revisions.register_object(
                GovernanceObject(
                    object_id=approval.object_id,
                    tenant_id=approval.tenant_id,
                    object_type="Approval",
                    created_at=approval.created_at,
                    created_by_actor_id=approval.created_by_actor_id,
                )
            )
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_approvals(
                record_id, tenant_id, object_id, revision, subject_object_id,
                subject_revision, decision, content_hash, schema_version,
                created_at, created_by_actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.record_id,
                approval.tenant_id,
                approval.object_id,
                approval.revision,
                approval.subject_object_id,
                approval.subject_revision,
                approval.decision,
                approval.content_hash or "sha256:approval",
                approval.schema_version,
                approval.created_at.isoformat(),
                approval.created_by_actor_id,
            ),
        )

    def actor_may_transition(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        subject_object_id: str,
        subject_revision: int,
        workspace_object_id: str | None,
        at: datetime,
        permission: str = "transition_task",
    ) -> tuple[bool, str | None]:
        """Return (permitted, deny_reason_code)."""

        # Role assignment path
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
            # Fail closed: subject workspace must be known for workspace-scoped work.
            if workspace_object_id is None:
                continue
            # Prefer explicit workspace FK when present.
            if (
                assignment.workspace_object_id is not None
                and assignment.workspace_object_id != workspace_object_id
            ):
                continue
            # Always enforce jurisdiction for workspace-scoped assignments.
            if assignment.jurisdiction_key == "workspace":
                if assignment.jurisdiction_value != workspace_object_id:
                    continue
            elif assignment.jurisdiction_key not in {"tenant", "*"}:
                # Unknown jurisdiction keys do not authorize.
                continue
            permissions = set(json.loads(str(row["permissions_json"])))
            if permission in permissions or "*" in permissions:
                return True, None

        # Grant path
        grant_rows = self._conn.execute(
            """
            SELECT * FROM gov_delegated_grants
            WHERE tenant_id = ? AND recipient_actor_id = ?
              AND subject_object_id = ? AND permission = ?
            """,
            (tenant_id, actor_id, subject_object_id, permission),
        ).fetchall()
        last_deny = ReasonCode.DENY_MISSING_AUTHORITY.value
        if not grant_rows:
            return False, last_deny
        for grow in grant_rows:
            if not grow["issuance_basis_kind"] or not grow["issuance_basis_id"]:
                # Migrations must not invent authority for historical grant rows.
                continue
            grant = DelegatedGrant(
                grant_id=str(grow["grant_id"]),
                tenant_id=str(grow["tenant_id"]),
                delegator_actor_id=str(grow["delegator_actor_id"]),
                recipient_actor_id=str(grow["recipient_actor_id"]),
                permission=str(grow["permission"]),
                subject_object_id=str(grow["subject_object_id"]),
                subject_revision=int(grow["subject_revision"]),
                effective_from=datetime.fromisoformat(str(grow["effective_from"])),
                expires_at=datetime.fromisoformat(str(grow["expires_at"])),
                created_at=datetime.fromisoformat(str(grow["created_at"])),
                created_by_actor_id=str(grow["created_by_actor_id"]),
                issuance_basis_kind=str(grow["issuance_basis_kind"]),
                issuance_basis_id=str(grow["issuance_basis_id"]),
                redelegatable=bool(grow["redelegatable"]),
                schema_version=str(grow["schema_version"]),
            )
            rev_row = self._conn.execute(
                """
                SELECT * FROM gov_revocation_decisions
                WHERE tenant_id = ? AND grant_id = ?
                """,
                (tenant_id, grant.grant_id),
            ).fetchone()
            revocation = None
            if rev_row is not None:
                revocation = RevocationDecision(
                    revocation_id=str(rev_row["revocation_id"]),
                    tenant_id=str(rev_row["tenant_id"]),
                    grant_id=str(rev_row["grant_id"]),
                    created_at=datetime.fromisoformat(str(rev_row["created_at"])),
                    created_by_actor_id=str(rev_row["created_by_actor_id"]),
                    rationale=str(rev_row["rationale"]),
                    schema_version=str(rev_row["schema_version"]),
                )
            try:
                assert_grant_authorizes(
                    grant,
                    at=at,
                    recipient_actor_id=actor_id,
                    subject_object_id=subject_object_id,
                    subject_revision=subject_revision,
                    permission=permission,
                    revocation=revocation,
                )
                return True, None
            except GrantExpiredError:
                last_deny = ReasonCode.DENY_GRANT_EXPIRED.value
            except GrantRevokedError:
                last_deny = ReasonCode.DENY_GRANT_REVOKED.value
            except GrantWrongRevisionError:
                last_deny = ReasonCode.DENY_GRANT_WRONG_REVISION.value

        return False, last_deny

    def approval_revision_for(
        self, *, tenant_id: str, subject_object_id: str
    ) -> int | None:
        row = self._conn.execute(
            """
            SELECT subject_revision FROM gov_approvals
            WHERE tenant_id = ? AND subject_object_id = ? AND decision = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, subject_object_id),
        ).fetchone()
        return int(row[0]) if row else None

    def approvals_satisfy(
        self,
        *,
        tenant_id: str,
        subject_object_id: str,
        subject_revision: int,
        required: int,
        workspace_object_id: str | None,
        at: datetime,
    ) -> tuple[bool, int | None, tuple[str, ...]]:
        """Return (ok, matched_revision, authorized_approver_ids).

        Counts distinct authorized approvers for the exact subject revision.
        Approvers must hold the ``approve`` permission (or ``*``).
        """

        if required < 1:
            return True, None, ()
        rows = self._conn.execute(
            """
            SELECT DISTINCT created_by_actor_id
            FROM gov_approvals
            WHERE tenant_id = ?
              AND subject_object_id = ?
              AND subject_revision = ?
              AND decision = 'approved'
            ORDER BY created_by_actor_id
            """,
            (tenant_id, subject_object_id, subject_revision),
        ).fetchall()
        authorized: list[str] = []
        for row in rows:
            approver_id = str(row[0])
            permitted, _ = self.actor_may_transition(
                tenant_id=tenant_id,
                actor_id=approver_id,
                subject_object_id=subject_object_id,
                subject_revision=subject_revision,
                workspace_object_id=workspace_object_id,
                at=at,
                permission="approve",
            )
            if permitted:
                authorized.append(approver_id)
        if len(authorized) >= required:
            return True, subject_revision, tuple(authorized)
        return False, None, tuple(authorized)
