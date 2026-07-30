"""Integrated governance scenario proofs against persisted records (M1-024)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holodeck_control_plane.governance_commands import (
    governance_mutation_entrypoints,
    submit_governance_command,
)
from holodeck_governance.domain.authority.grants import (
    DelegatedGrant,
    RevocationDecision,
    assert_grant_authorizes,
)
from holodeck_governance.domain.catalogs import SCENARIO_CATALOG_EXPECTATIONS
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.commands import CommandEnvelope
from holodeck_governance.domain.edges import TraceabilityEdge, validate_edge_endpoints
from holodeck_governance.domain.errors import (
    EdgeValidationError,
    IdempotencyConflictError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.legacy_mapping import dry_run_mapping
from holodeck_governance.domain.policy.binding import (
    PolicyUnauthorizedRelaxationError,
    merge_policy_parameters,
)
from holodeck_governance.domain.revisions import (
    ObjectRevision,
    assert_revision_immutable,
    content_hash_for,
)
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.command_service import CommandService
from holodeck_governance.storage.sqlite.legacy_import import import_legacy_tasks
from holodeck_governance.storage.sqlite.outbox import OutboxWorker
from holodeck_governance.storage.sqlite.reconstruction import (
    receipt_reason_codes,
    reconstruct_from_command,
)
from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository
from holodeck_governance.testing import FixtureIds, PACKET_SCENARIO_OWNERS
from holodeck_governance.testing.seed import seed_authorized_task_world


def _world(**kwargs):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn, **kwargs)
    return CommandService(conn), world, conn


def _cmd(world, **overrides) -> CommandEnvelope:
    base = dict(
        command_id=generate_uuidv7(),
        command_type="task.transition",
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        target_object_id=world["task_object_id"],
        expected_revision=1,
        idempotency_key=generate_uuidv7(),
        payload_schema_version="m1.command.task_transition.v1",
        correlation_id=generate_uuidv7(),
        issued_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        payload={"to_state": "ready"},
    )
    base.update(overrides)
    return CommandEnvelope(**base)


def test_gs001_tenant_isolation_receipt_without_success() -> None:
    service, world, conn = _world()
    beta = FixtureIds().tenant_beta
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (beta, datetime(2026, 7, 24, 12, 0, tzinfo=UTC).isoformat(), world["actor_id"]),
    )
    conn.commit()
    receipt = service.handle(_cmd(world, tenant_id=beta))
    assert receipt.outcome == "rejected"
    assert receipt.error_code == DomainErrorCode.CROSS_TENANT_ACCESS.value
    assert conn.execute("SELECT COUNT(*) FROM gov_domain_events").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0


def test_gs002_revision_immutability_and_correction() -> None:
    from holodeck_governance.domain.registry import GovernanceObject
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
    from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant

    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    revisions = SqliteRevisionRepository(conn)
    obj = GovernanceObject(
        object_id=ids.mission_object,
        tenant_id=ids.tenant_alpha,
        object_type="Mission",
        created_at=now,
        created_by_actor_id=ids.human_owner,
    )
    first = revisions.create_initial_revision(obj=obj, payload={"summary": "v1"})
    with pytest.raises(RevisionImmutableError):
        assert_revision_immutable(first)
    with pytest.raises(RevisionImmutableError):
        revisions.reject_in_place_mutation(ids.mission_object, 1)
    corrected = revisions.append_correction(
        object_id=ids.mission_object,
        tenant_id=ids.tenant_alpha,
        actor_id=ids.human_owner,
        created_at=now,
        payload={"summary": "v2"},
        expected_head_revision=1,
    )
    assert corrected.revision == 2
    assert corrected.supersedes_revision == 1
    head = revisions.get_head(ids.mission_object)
    assert head is not None and head.head_revision == 2
    still = revisions.get_revision(ids.mission_object, 1)
    assert still is not None and still.payload["summary"] == "v1"


def test_gs003_stale_approval_blocks_transition() -> None:
    from holodeck_governance.domain.policy.binding import PolicyBinding
    from holodeck_governance.domain.records.review import ApprovalRecord
    from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository

    service, world, conn = _world(permissions=("transition_task", "approve"))
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    auth = SqliteAuthorityRepository(conn)
    SqlitePolicyRepository(conn).save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "1"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=10,
            effective_from=now,
        )
    )
    auth.save_approval(
        ApprovalRecord(
            record_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            object_id=generate_uuidv7(),
            revision=1,
            subject_object_id=world["task_object_id"],
            subject_revision=1,
            created_at=now,
            created_by_actor_id=world["actor_id"],
            decision="approved",
        )
    )
    conn.commit()
    # Advance task head to rev 2 via allowed transition first
    assert service.handle(_cmd(world, idempotency_key="prep")).outcome == "accepted"
    receipt = service.handle(
        _cmd(
            world,
            expected_revision=2,
            idempotency_key="stale-appr",
            payload={"to_state": "active"},
        )
    )
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_STALE_APPROVAL.value in receipt.reason_codes


def test_gs004_delegated_grant_paths() -> None:
    service, world, conn = _world(permissions=("delegate:transition_task",))
    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    auth = SqliteAuthorityRepository(conn)
    auth.save_actor(
        __import__(
            "holodeck_governance.domain.authority.actors", fromlist=["Actor", "ActorKind"]
        ).Actor(
            actor_id=ids.worker_agent,
            tenant_id=world["tenant_id"],
            kind=__import__(
                "holodeck_governance.domain.authority.actors", fromlist=["ActorKind"]
            ).ActorKind.AGENT,
            display_name="Worker",
            created_at=now,
            created_by_actor_id=world["actor_id"],
        )
    )
    grant = DelegatedGrant(
        grant_id=generate_uuidv7(),
        tenant_id=world["tenant_id"],
        delegator_actor_id=world["actor_id"],
        recipient_actor_id=ids.worker_agent,
        permission="transition_task",
        subject_object_id=world["task_object_id"],
        subject_revision=1,
        effective_from=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
        created_at=now,
        created_by_actor_id=world["actor_id"],
        issuance_basis_id=world["role_assignment_id"],
    )
    auth.save_grant(grant)
    conn.commit()
    allowed = service.handle(
        _cmd(world, actor_id=ids.worker_agent, idempotency_key="grant-ok")
    )
    assert allowed.outcome == "accepted"
    # Wrong revision grant cannot authorize a later head
    world2_conn = sqlite3.connect(":memory:")
    world2_conn.row_factory = sqlite3.Row
    world2 = seed_authorized_task_world(world2_conn, permissions=("delegate:transition_task",))
    auth2 = SqliteAuthorityRepository(world2_conn)
    auth2.save_actor(
        __import__(
            "holodeck_governance.domain.authority.actors", fromlist=["Actor", "ActorKind"]
        ).Actor(
            actor_id=ids.worker_agent,
            tenant_id=world2["tenant_id"],
            kind=__import__(
                "holodeck_governance.domain.authority.actors", fromlist=["ActorKind"]
            ).ActorKind.AGENT,
                display_name="Worker",
                created_at=now,
                created_by_actor_id=world2["actor_id"],
            )
    )
    expired = DelegatedGrant(
        grant_id=generate_uuidv7(),
        tenant_id=world2["tenant_id"],
        delegator_actor_id=world2["actor_id"],
        recipient_actor_id=ids.worker_agent,
        permission="transition_task",
        subject_object_id=world2["task_object_id"],
        subject_revision=1,
        effective_from=now - timedelta(hours=2),
        expires_at=now - timedelta(minutes=1),
            created_at=now,
            created_by_actor_id=world2["actor_id"],
            issuance_basis_id=world2["role_assignment_id"],
        )
    auth2.save_grant(expired)
    world2_conn.commit()
    denied = CommandService(world2_conn).handle(
        _cmd(
            world2,
            actor_id=ids.worker_agent,
            idempotency_key="grant-expired",
            issued_at=now,
        )
    )
    assert denied.outcome == "rejected"
    assert ReasonCode.DENY_GRANT_EXPIRED.value in denied.reason_codes


def test_gs005_edge_integrity() -> None:
    from holodeck_governance.domain.registry import GovernanceObject
    from holodeck_governance.domain.revisions import ObjectRevision, content_hash_for
    from holodeck_governance.storage.sqlite.edges import SqliteEdgeRepository
    from holodeck_governance.storage.sqlite.revisions import SqliteRevisionRepository
    from holodeck_governance.storage.sqlite.tenants import ensure_default_local_tenant

    ids = FixtureIds()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_default_local_tenant(
        conn, tenant_id=ids.tenant_alpha, created_by_actor_id=ids.system_service
    )
    conn.execute(
        """
        INSERT INTO gov_tenants(
            tenant_id, slug, display_name, schema_version, created_at,
            created_by_actor_id, provenance_ref, status, is_default_local
        ) VALUES (?, 'beta', 'Beta', 'm1.tenant.v1', ?, ?, NULL, 'active', 0)
        """,
        (ids.tenant_beta, now.isoformat(), ids.system_service),
    )
    revisions = SqliteRevisionRepository(conn)
    edges = SqliteEdgeRepository(conn)

    def register(object_id: str, tenant_id: str, object_type: str) -> None:
        revisions.register_object(
            GovernanceObject(
                object_id=object_id,
                tenant_id=tenant_id,
                object_type=object_type,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
        rev = ObjectRevision(
            revision_id=generate_uuidv7(),
            tenant_id=tenant_id,
            object_id=object_id,
            revision=1,
            content_hash=content_hash_for({"t": object_type}),
            payload={"t": object_type},
            created_at=now,
            created_by_actor_id=ids.human_owner,
            finalized=True,
        )
        revisions._insert_revision(rev)
        revisions._upsert_head(rev)

    evidence_id = generate_uuidv7()
    requirement_id = ids.requirement_object
    register(evidence_id, ids.tenant_alpha, "Evidence")
    register(requirement_id, ids.tenant_alpha, "Requirement")
    with pytest.raises(EdgeValidationError):
        edges.save(
            TraceabilityEdge(
                edge_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                edge_type="evidence_supports_requirement",
                from_object_id=generate_uuidv7(),
                from_revision=1,
                to_object_id=requirement_id,
                to_revision=1,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
    mission_id = generate_uuidv7()
    register(mission_id, ids.tenant_alpha, "Mission")
    with pytest.raises(EdgeValidationError):
        edges.save(
            TraceabilityEdge(
                edge_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                edge_type="evidence_supports_requirement",
                from_object_id=mission_id,
                from_revision=1,
                to_object_id=requirement_id,
                to_revision=1,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
    from holodeck_governance.domain.errors import CrossTenantAccessError

    beta_req = generate_uuidv7()
    register(beta_req, ids.tenant_beta, "Requirement")
    with pytest.raises(CrossTenantAccessError):
        edges.save(
            TraceabilityEdge(
                edge_id=generate_uuidv7(),
                tenant_id=ids.tenant_alpha,
                edge_type="evidence_supports_requirement",
                from_object_id=evidence_id,
                from_revision=1,
                to_object_id=beta_req,
                to_revision=1,
                created_at=now,
                created_by_actor_id=ids.human_owner,
            )
        )
    assert conn.execute("SELECT COUNT(*) FROM gov_traceability_edges").fetchone()[0] == 0


def test_gs006_lifecycle_via_command() -> None:
    service, world, _ = _world()
    assert service.handle(_cmd(world)).outcome == "accepted"
    bad = service.handle(
        _cmd(world, expected_revision=2, payload={"to_state": "accepted"})
    )
    assert bad.outcome == "rejected"
    assert ReasonCode.DENY_INVALID_TRANSITION.value in bad.reason_codes


def test_gs007_idempotency_retry_and_conflict() -> None:
    service, world, _ = _world()
    first = service.handle(_cmd(world, idempotency_key="idem-1"))
    second = service.handle(
        _cmd(world, command_id=generate_uuidv7(), idempotency_key="idem-1")
    )
    assert first.receipt_id == second.receipt_id
    with pytest.raises(IdempotencyConflictError):
        service.handle(
            _cmd(
                world,
                idempotency_key="idem-1",
                payload={"to_state": "blocked"},
            )
        )


def test_gs008_evaluation_reproducibility_via_command() -> None:
    service, world, conn = _world()
    receipt = service.handle(_cmd(world))
    reconstructed = reconstruct_from_command(
        conn, tenant_id=world["tenant_id"], command_id=receipt.command_id
    )
    assert reconstructed.evaluation_result is not None
    assert ReasonCode.ALLOWED.value in receipt_reason_codes(reconstructed.receipt)
    result = reconstructed.evaluation_result
    assert result.get("primitive_results_json")
    primitives = __import__("json").loads(str(result["primitive_results_json"]))
    assert primitives
    assert result.get("evaluator_implementation_id")
    assert reconstructed.evaluation_snapshot is not None
    snap = reconstructed.evaluation_snapshot
    assert snap.get("input_refs_json")
    # Reproduce from persisted result columns
    from holodeck_governance.storage.sqlite.repos import SqliteEvaluationRepository

    loaded = SqliteEvaluationRepository(conn).load_result(
        world["tenant_id"], str(result["result_id"])
    )
    assert loaded is not None
    assert loaded.primitive_results
    assert loaded.outcome == "allow"


def test_gs009_policy_precedence() -> None:
    from holodeck_governance.domain.policy.binding import PolicyBinding
    from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository

    with pytest.raises(PolicyUnauthorizedRelaxationError):
        merge_policy_parameters(
            {"required_approvals": "2"},
            {"required_approvals": "1"},
            allow_relaxation=False,
        )
    service, world, conn = _world()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    policy = SqlitePolicyRepository(conn)
    policy.save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "1"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=10,
            effective_from=now,
        )
    )
    policy.save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            scope="workspace",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "2"},
            created_at=now,
            created_by_actor_id=world["actor_id"],
            precedence=20,
            effective_from=now,
        )
    )
    conn.commit()
    # Tightened required_approvals=2 still blocks without any approval row.
    receipt = service.handle(_cmd(world, idempotency_key="policy-active"))
    assert receipt.outcome == "rejected"
    assert ReasonCode.DENY_STALE_APPROVAL.value in receipt.reason_codes
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 0
    # One authorized approval is insufficient when required_approvals=2.
    from holodeck_governance.domain.records.review import ApprovalRecord
    from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository

    conn2 = sqlite3.connect(":memory:")
    conn2.row_factory = sqlite3.Row
    world2 = seed_authorized_task_world(
        conn2, permissions=("transition_task", "approve")
    )
    policy2 = SqlitePolicyRepository(conn2)
    now2 = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    policy2.save(
        PolicyBinding(
            binding_id=generate_uuidv7(),
            tenant_id=world2["tenant_id"],
            scope="tenant",
            evaluator_id="m1.TaskTransitionEvaluator.v1",
            parameters={"required_approvals": "2"},
            created_at=now2,
            created_by_actor_id=world2["actor_id"],
            precedence=10,
            effective_from=now2,
        )
    )
    SqliteAuthorityRepository(conn2).save_approval(
        ApprovalRecord(
            record_id=generate_uuidv7(),
            tenant_id=world2["tenant_id"],
            object_id=generate_uuidv7(),
            revision=1,
            subject_object_id=world2["task_object_id"],
            subject_revision=1,
            created_at=now2,
            created_by_actor_id=world2["actor_id"],
            decision="approved",
        )
    )
    conn2.commit()
    one_of_two = CommandService(conn2).handle(
        _cmd(world2, idempotency_key="one-of-two")
    )
    assert one_of_two.outcome == "rejected"
    assert ReasonCode.DENY_STALE_APPROVAL.value in one_of_two.reason_codes


def test_gs010_atomic_success_fault_injection() -> None:
    service, world, conn = _world()
    service._fault_before = "outbox"
    with pytest.raises(RuntimeError, match="injected fault before outbox"):
        service.handle(_cmd(world))
    assert conn.execute("SELECT COUNT(*) FROM gov_command_receipts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0
    task = SqliteTaskRepository(conn).get_head_task(world["task_object_id"])
    assert task is not None and task.state == "draft"


def test_gs011_auditable_rejection_table() -> None:
    service, world, conn = _world()
    missing = service.handle(
        _cmd(world, target_object_id=generate_uuidv7(), idempotency_key="missing")
    )
    assert missing.outcome == "rejected"
    stale = service.handle(_cmd(world, expected_revision=9, idempotency_key="stale"))
    assert ReasonCode.DENY_STALE_REVISION.value in stale.reason_codes
    assert conn.execute("SELECT COUNT(*) FROM gov_outbox_items").fetchone()[0] == 0


def test_gs012_outbox_recovery_preserves_decision() -> None:
    service, world, conn = _world()
    service.handle(_cmd(world))
    worker = OutboxWorker(conn, max_attempts=2)
    now = datetime(2026, 7, 24, 12, 1, tzinfo=UTC)
    item = worker.claim(worker_id="w1", now=now)
    assert item is not None
    worker.record_attempt(
        item,
        success=False,
        now=now,
        subject_object_id=world["task_object_id"],
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        lease_owner="w1",
    )
    conn.execute(
        "UPDATE gov_outbox_items SET next_attempt_at = ? WHERE outbox_item_id = ?",
        (now.isoformat(), item),
    )
    conn.commit()
    reclaimed = worker.claim(worker_id="w1", now=now)
    assert reclaimed == item
    dead = worker.record_attempt(
        item,
        success=False,
        now=now,
        subject_object_id=world["task_object_id"],
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        lease_owner="w1",
    )
    assert dead is not None
    assert conn.execute("SELECT COUNT(*) FROM gov_transition_records").fetchone()[0] == 1


def test_gs013_reconstruction_includes_evaluation_graph() -> None:
    from holodeck_governance.domain.edges import TraceabilityEdge
    from holodeck_governance.storage.sqlite.graph_seed import (
        persist_edge,
        seed_reconstruction_graph,
    )

    service, world, conn = _world()
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    requirement_id = FixtureIds().requirement_object
    evidence_id = generate_uuidv7()
    seed_reconstruction_graph(
        conn,
        tenant_id=world["tenant_id"],
        actor_id=world["actor_id"],
        subject_object_id=world["task_object_id"],
        requirement_object_id=requirement_id,
        evidence_object_id=evidence_id,
        now=now,
    )
    persist_edge(
        conn,
        TraceabilityEdge(
            edge_id=generate_uuidv7(),
            tenant_id=world["tenant_id"],
            edge_type="task_belongs_to_mission",
            from_object_id=world["task_object_id"],
            from_revision=1,
            to_object_id=world["mission_object_id"],
            to_revision=1,
            created_at=now,
            created_by_actor_id=world["actor_id"],
        ),
    )
    conn.commit()
    command = _cmd(world)
    receipt = service.handle(command)
    reconstructed = reconstruct_from_command(
        conn, tenant_id=world["tenant_id"], command_id=command.command_id
    )
    assert reconstructed.receipt["outcome"] == "accepted"
    assert reconstructed.evaluation_result is not None
    assert reconstructed.evaluation_snapshot is not None
    assert reconstructed.transitions
    assert reconstructed.outbox_items
    assert reconstructed.edges
    assert reconstructed.policy_bindings
    assert reconstructed.grants
    assert reconstructed.decisions
    assert reconstructed.decisions[0]["outcome"] == "accepted"
    assert receipt.evaluation_result_id == reconstructed.evaluation_result["result_id"]


def test_gs014_legacy_import_no_fabricated_authority(tmp_path: Path) -> None:
    from holodeck_control_plane.store import Store

    db = tmp_path / "legacy.db"
    store = Store(db)
    store.create_workspace({"workspace_id": "ws-alpha", "name": "Alpha"})
    store.create_task(
        "ws-alpha",
        {"task_id": "task-1", "title": "Legacy", "status": "in-progress"},
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    imported = import_legacy_tasks(
        conn,
        tenant_id=FixtureIds().tenant_alpha,
        actor_id=FixtureIds().system_service,
    )
    assert len(imported) == 1
    assert imported[0].provenance_kind == "legacy_import"
    mapped = dry_run_mapping([("thin_slice", "acceptance_decisions")])
    assert mapped[0]["disposition"] == "unsupported"


def test_adapter_boundary_uses_governance_commands(tmp_path: Path) -> None:
    db = str(tmp_path / "gov.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    world = seed_authorized_task_world(conn)
    conn.close()
    receipt = submit_governance_command(db, _cmd(world))
    assert receipt.outcome == "accepted"
    assert governance_mutation_entrypoints() == (
        "holodeck_control_plane.governance_commands.submit_governance_command",
    )
    store_src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "holodeck_control_plane"
        / "store.py"
    ).read_text(encoding="utf-8")
    assert "gov_" not in store_src


def test_scenario_catalogue_complete_for_m1_024() -> None:
    assert set(SCENARIO_CATALOG_EXPECTATIONS) == {f"GS-{i:03d}" for i in range(1, 15)}
    assert set(PACKET_SCENARIO_OWNERS["M1-024"]) == set(SCENARIO_CATALOG_EXPECTATIONS)
