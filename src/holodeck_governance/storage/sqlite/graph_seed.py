"""Helpers to persist reconstruction-graph rows for GS-013 fixtures."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from holodeck_governance.domain.authority.grants import DelegatedGrant
from holodeck_governance.domain.edges import TraceabilityEdge
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.policy.binding import PolicyBinding
from holodeck_governance.domain.provenance.external_reference import ExternalReference
from holodeck_governance.domain.registry import GovernanceObject
from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for
from holodeck_governance.storage.sqlite.edges import SqliteEdgeRepository
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository
from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository


def ensure_graph_tables(conn: sqlite3.Connection) -> None:
    migrate_governance(conn)


def persist_edge(conn: sqlite3.Connection, edge: TraceabilityEdge) -> None:
    """Persist an edge only after domain endpoint validation succeeds."""

    SqliteEdgeRepository(conn).save(edge)


def persist_external_reference(conn: sqlite3.Connection, ref: ExternalReference) -> None:
    ensure_graph_tables(conn)
    conn.execute(
        """
        INSERT INTO gov_external_references(
            reference_id, tenant_id, provider, object_type, external_object_id,
            locator, observed_at, created_at, created_by_actor_id, subject_object_id,
            content_hash, schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ref.reference_id,
            ref.tenant_id,
            ref.provider,
            ref.object_type,
            ref.external_object_id,
            ref.locator,
            ref.observed_at.isoformat(),
            ref.created_at.isoformat(),
            ref.created_by_actor_id,
            ref.subject_object_id,
            ref.content_hash,
            ref.schema_version,
        ),
    )


def persist_policy_binding(conn: sqlite3.Connection, binding: PolicyBinding) -> None:
    SqlitePolicyRepository(conn).save(binding)


def persist_grant(conn: sqlite3.Connection, grant: DelegatedGrant) -> None:
    ensure_graph_tables(conn)
    conn.execute(
        """
        INSERT INTO gov_delegated_grants(
            grant_id, tenant_id, delegator_actor_id, recipient_actor_id, permission,
            subject_object_id, subject_revision, effective_from, expires_at,
            created_at, created_by_actor_id, redelegatable, schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if grant.redelegatable else 0,
            grant.schema_version,
        ),
    )


def _ensure_typed_object(
    conn: sqlite3.Connection,
    *,
    object_id: str,
    tenant_id: str,
    object_type: str,
    actor_id: str,
    now: datetime,
) -> None:
    revisions = SqliteRevisionRepository(conn)
    if revisions.get_object(object_id) is not None:
        return
    revisions.register_object(
        GovernanceObject(
            object_id=object_id,
            tenant_id=tenant_id,
            object_type=object_type,
            created_at=now,
            created_by_actor_id=actor_id,
        )
    )
    rev = ObjectRevision(
        revision_id=generate_uuidv7(),
        tenant_id=tenant_id,
        object_id=object_id,
        revision=1,
        content_hash=content_hash_for({"kind": object_type}),
        payload={"kind": object_type},
        created_at=now,
        created_by_actor_id=actor_id,
        finalized=True,
    )
    revisions._insert_revision(rev)
    revisions._upsert_head(rev)


def seed_reconstruction_graph(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_id: str,
    subject_object_id: str,
    requirement_object_id: str,
    evidence_object_id: str,
    now: datetime,
) -> None:
    """Populate edges/refs/policy/grant rows used by GS-013 reconstruction."""

    ensure_graph_tables(conn)
    _ensure_typed_object(
        conn,
        object_id=requirement_object_id,
        tenant_id=tenant_id,
        object_type="Requirement",
        actor_id=actor_id,
        now=now,
    )
    _ensure_typed_object(
        conn,
        object_id=evidence_object_id,
        tenant_id=tenant_id,
        object_type="Evidence",
        actor_id=actor_id,
        now=now,
    )
    persist_edge(
        conn,
        TraceabilityEdge(
            edge_id=generate_uuidv7(),
            tenant_id=tenant_id,
            edge_type="evidence_supports_requirement",
            from_object_id=evidence_object_id,
            from_revision=1,
            to_object_id=requirement_object_id,
            to_revision=1,
            created_at=now,
            created_by_actor_id=actor_id,
        ),
    )
    persist_external_reference(
        conn,
        ExternalReference(
            reference_id=generate_uuidv7(),
            tenant_id=tenant_id,
            provider="artifact-store",
            object_type="EvidenceBlob",
            external_object_id="blob-1",
            locator="artifact://blob-1",
            observed_at=now,
            created_at=now,
            created_by_actor_id=actor_id,
            subject_object_id=evidence_object_id,
            content_hash="sha256:evidence",
        ),
    )
    persist_policy_binding(
        conn,
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=tenant_id,
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "0"},
            created_at=now,
            created_by_actor_id=actor_id,
            precedence=10,
            effective_from=now,
        ),
    )
    persist_grant(
        conn,
        DelegatedGrant(
            grant_id=generate_uuidv7(),
            tenant_id=tenant_id,
            delegator_actor_id=actor_id,
            recipient_actor_id=actor_id,
            permission="transition_task",
            subject_object_id=subject_object_id,
            subject_revision=1,
            effective_from=now,
            expires_at=now + timedelta(days=365),
            created_at=now,
            created_by_actor_id=actor_id,
            issuance_basis_id=str(
                conn.execute(
                    "SELECT assignment_id FROM gov_role_assignments WHERE tenant_id = ? AND actor_id = ? LIMIT 1",
                    (tenant_id, actor_id),
                ).fetchone()[0]
            ),
        ),
    )
    conn.commit()
