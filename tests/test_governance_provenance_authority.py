"""Tests for legacy mapping, provenance, external refs, and actors."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from holodeck_governance.domain.authority.actors import Actor, ActorKind
from holodeck_governance.domain.authority.roles import RoleProfile, with_content_hash
from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import RevisionImmutableError
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.legacy_mapping import (
    dry_run_mapping,
    map_legacy_status,
    asserts_no_fabricated_authority,
)
from holodeck_governance.domain.provenance.external_reference import (
    ExternalReference,
    external_reference_dedupe_key,
)
from holodeck_governance.domain.provenance_records import (
    EpistemicStatus,
    ProvenanceRecord,
    TrustClass,
    TrustClassification,
    promote_trust,
    reject_trust_in_place_edit,
)
from holodeck_governance.testing import FixtureIds


def test_legacy_mapping_is_deterministic_and_complete() -> None:
    rows = [
        ("task", "backlog"),
        ("task", "ready"),
        ("task", "in-progress"),
        ("task", "review"),
        ("task", "blocked"),
        ("task", "done"),
        ("task", "cancelled"),
        ("run", "active"),
        ("run", "completed"),
        ("run", "failed"),
        ("run", "cancelled"),
        ("claim", "active"),
        ("claim", "released"),
        ("thin_slice", "missions"),
    ]
    first = dry_run_mapping(rows)
    second = dry_run_mapping(rows)
    assert first == second
    assert map_legacy_status("task", "in-progress").m1_value == "active"
    assert first[-1]["disposition"] == "unsupported"
    assert first[-1]["error_code"] == DomainErrorCode.UNSUPPORTED_LEGACY_MAPPING.value
    assert "Approval" in asserts_no_fabricated_authority()


def test_trust_promotion_retains_origin_and_blocks_in_place_edit() -> None:
    ids = FixtureIds()
    origin = ProvenanceRecord(
        provenance_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        subject_object_id=ids.mission_object,
        origin_kind="manual",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.human_owner,
    )
    trust = TrustClassification(
        trust_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        subject_object_id=ids.mission_object,
        trust_class=TrustClass.CLAIMED,
        epistemic_status=EpistemicStatus.UNVERIFIED,
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.human_owner,
    )
    with pytest.raises(RevisionImmutableError):
        reject_trust_in_place_edit(trust)
    promoted, decision = promote_trust(
        existing=trust,
        new_trust_id=generate_uuidv7(),
        validation_id=generate_uuidv7(),
        actor_id=ids.human_reviewer,
        created_at=datetime(2026, 7, 24, 12, 5, tzinfo=UTC),
        to_trust_class=TrustClass.VALIDATED,
        to_epistemic=EpistemicStatus.VALIDATED,
        rationale="reviewed",
    )
    assert promoted.supersedes_trust_id == trust.trust_id
    assert decision.from_trust_id == trust.trust_id
    assert decision.to_trust_id == promoted.trust_id
    assert origin.subject_object_id == trust.subject_object_id


def test_external_reference_dedupe_is_tenant_scoped() -> None:
    ids = FixtureIds()
    left = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="buzz",
        object_type="message",
        external_object_id="msg-1",
        locator="buzz://msg-1",
        observed_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.system_service,
        subject_object_id=ids.mission_object,
    )
    right = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_alpha,
        provider="buzz",
        object_type="message",
        external_object_id="msg-1",
        locator="buzz://msg-1",
        observed_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.system_service,
    )
    other_tenant = ExternalReference(
        reference_id=generate_uuidv7(),
        tenant_id=ids.tenant_beta,
        provider="buzz",
        object_type="message",
        external_object_id="msg-1",
        locator="buzz://msg-1",
        observed_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.system_service,
    )
    assert external_reference_dedupe_key(left) == external_reference_dedupe_key(right)
    assert external_reference_dedupe_key(left) != external_reference_dedupe_key(other_tenant)
    assert left.reference_id != "msg-1"


def test_actors_and_role_revisions_remain_distinct() -> None:
    ids = FixtureIds()
    human = Actor(
        actor_id=ids.human_owner,
        tenant_id=ids.tenant_alpha,
        kind=ActorKind.HUMAN,
        display_name="Owner",
        created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        created_by_actor_id=ids.system_service,
    )
    role_object = generate_uuidv7()
    v1 = with_content_hash(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object,
            revision=1,
            name="reviewer",
            permissions=("approve_mission",),
            jurisdiction={"workspace": ids.workspace_alpha_1},
            created_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            created_by_actor_id=ids.system_service,
        )
    )
    v2 = with_content_hash(
        RoleProfile(
            role_profile_id=generate_uuidv7(),
            tenant_id=ids.tenant_alpha,
            role_object_id=role_object,
            revision=2,
            name="reviewer",
            permissions=("approve_mission", "escalate"),
            jurisdiction={"workspace": ids.workspace_alpha_1},
            created_at=datetime(2026, 7, 24, 12, 1, tzinfo=UTC),
            created_by_actor_id=ids.system_service,
            supersedes_revision=1,
        )
    )
    assert human.kind is ActorKind.HUMAN
    assert v1.role_object_id == v2.role_object_id
    assert v1.content_hash != v2.content_hash
    assert v1.revision == 1
