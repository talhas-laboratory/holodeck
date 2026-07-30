"""M2-018 Slack-shaped messy-thread acceptance fixture.

Plan
----
Model a noisy Slack-like channel thread (jokes, tangents, duplicate chatter,
truncated older history, mid-thread files) ending in an explicit Holodeck intake
request with attachments. Run that through the memory adapter + intake
orchestrator and assert the *manifest capture shape*.

This is intentionally not a semantic extraction test. M2-018 must retain
opaque reconstitution refs for the whole retrieved window — including noise —
so a later context compiler can decide relevance. Assertions therefore check
ids, relations, order, omissions, and anchor/attachment membership, not that
Holodeck "picked the right ideas" from the mess.
"""

from __future__ import annotations

from dataclasses import dataclass

from holodeck_governance.domain.collaboration import (
    ConversationContextManifestEntry,
    ProcessingOutcome,
)

from test_m2_e2e_memory_intake import _payload, _world

# Slack-shaped external ids (provider remains memory; locators are synthetic).
CHANNEL_ID = "C0PS-DEPLOY"
THREAD_ID = "T4821-claim-race"
ANCHOR_EVENT_ID = "S4821-final-intake"

# Human-readable transcript for the fixture narrative. Only the final body is
# submitted as the intake event; preceding rows become opaque manifest refs.
MESSY_SLACK_THREAD_TRANSCRIPT: tuple[dict[str, str], ...] = (
    {
        "external_id": "S4821-01",
        "role": "preceding",
        "text": "anyone looking at the deploy tonight?",
    },
    {
        "external_id": "S4821-02",
        "role": "preceding",
        "text": "lol ship it friday :ship:",
    },
    {
        "external_id": "S4821-03",
        "role": "preceding",
        "text": "the claim race is flaky again in coordination tests",
    },
    {
        "external_id": "S4821-04",
        "role": "preceding",
        "text": "also can someone order lunch for the war room",
    },
    {
        "external_id": "S4821-05",
        "role": "preceding",
        "text": "I already pinged oncall, ignore me",
    },
    {
        "external_id": "S4821-06-file",
        "role": "preceding_attachment",
        "text": "[file] earlier_error.png shared mid-thread",
    },
    {
        "external_id": "S4821-07",
        "role": "preceding",
        "text": "wait which PR was that again?",
    },
    {
        "external_id": ANCHOR_EVENT_ID,
        "role": "anchor",
        "text": (
            "@holodeck work: fix flaky claim race in coordination tests"
        ),
    },
)

ANCHOR_ATTACHMENTS: tuple[dict[str, object], ...] = (
    {
        "external_attachment_id": "F-logs-4821",
        "content_type": "text/plain",
        "locator": f"memory://slack-shaped/{CHANNEL_ID}/{THREAD_ID}/files/F-logs-4821",
        "content_hash": "sha256:logs-4821",
        "filename": "ci-logs.txt",
    },
    {
        "external_attachment_id": "F-stack-4821",
        "content_type": "image/png",
        "locator": f"memory://slack-shaped/{CHANNEL_ID}/{THREAD_ID}/files/F-stack-4821",
        "content_hash": "sha256:stack-4821",
        "filename": "stacktrace.png",
    },
)


@dataclass(frozen=True, slots=True)
class MessySlackThreadFixture:
    """Captured expectations for the Slack-shaped messy-thread scenario."""

    channel_id: str
    thread_id: str
    anchor_event_id: str
    preceding_message_ids: tuple[str, ...]
    preceding_attachment_ids: tuple[str, ...]
    omission_id: str
    omission_note: str
    anchor_attachment_ids: tuple[str, ...]
    subject_text: str
    body_text: str


def build_messy_slack_thread_fixture() -> MessySlackThreadFixture:
    preceding_message_ids = tuple(
        row["external_id"]
        for row in MESSY_SLACK_THREAD_TRANSCRIPT
        if row["role"] == "preceding"
    )
    preceding_attachment_ids = tuple(
        row["external_id"]
        for row in MESSY_SLACK_THREAD_TRANSCRIPT
        if row["role"] == "preceding_attachment"
    )
    anchor = next(
        row for row in MESSY_SLACK_THREAD_TRANSCRIPT if row["role"] == "anchor"
    )
    return MessySlackThreadFixture(
        channel_id=CHANNEL_ID,
        thread_id=THREAD_ID,
        anchor_event_id=ANCHOR_EVENT_ID,
        preceding_message_ids=preceding_message_ids,
        preceding_attachment_ids=preceding_attachment_ids,
        omission_id="omission:slack-shaped-window",
        omission_note="provider_history_window_truncated",
        anchor_attachment_ids=tuple(
            str(item["external_attachment_id"]) for item in ANCHOR_ATTACHMENTS
        ),
        subject_text="fix flaky claim race in coordination tests",
        body_text=anchor["text"],
    )


def _seed_messy_slack_thread(world, fixture: MessySlackThreadFixture) -> None:
    """Register truncated + noisy preceding history on the memory adapter."""

    entries: list[ConversationContextManifestEntry] = [
        ConversationContextManifestEntry(
            kind="omission",
            external_id=fixture.omission_id,
            locator="",
            relation="omission",
            sequence=0,
            note=fixture.omission_note,
        )
    ]
    sequence = 1
    for row in MESSY_SLACK_THREAD_TRANSCRIPT:
        if row["role"] == "anchor":
            continue
        if row["role"] == "preceding_attachment":
            entries.append(
                ConversationContextManifestEntry(
                    kind="attachment",
                    external_id=row["external_id"],
                    locator=(
                        f"memory://slack-shaped/{fixture.channel_id}/"
                        f"{fixture.thread_id}/files/{row['external_id']}"
                    ),
                    relation="attachment",
                    sequence=sequence,
                    note="mid_thread_share",
                )
            )
        else:
            entries.append(
                ConversationContextManifestEntry(
                    kind="message",
                    external_id=row["external_id"],
                    locator=(
                        f"memory://slack-shaped/{fixture.channel_id}/"
                        f"{fixture.thread_id}/messages/{row['external_id']}"
                    ),
                    relation="preceding",
                    sequence=sequence,
                )
            )
        sequence += 1

    world.adapter.seed_thread_context(
        tenant_id=world.ids.tenant_alpha,
        location_kind="thread",
        external_location_id=fixture.thread_id,
        entries=tuple(entries),
    )


def test_messy_slack_thread_fixture_captures_full_manifest_shape() -> None:
    """Acceptance: noisy Slack-shaped thread → complete ordered source manifest.

    Includes jokes/tangents on purpose. Capture must keep those refs; it must
    not silently drop "irrelevant" preceding messages.
    """

    fixture = build_messy_slack_thread_fixture()
    world = _world()
    _seed_messy_slack_thread(world, fixture)

    result = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id=fixture.anchor_event_id,
            body_text=fixture.body_text,
            location_kind="thread",
            external_location_id=fixture.thread_id,
            location_locator=(
                f"memory://slack-shaped/{fixture.channel_id}/threads/{fixture.thread_id}"
            ),
            parent_location_kind="channel",
            parent_external_location_id=fixture.channel_id,
            parent_location_locator=(
                f"memory://slack-shaped/channels/{fixture.channel_id}"
            ),
            event_locator=(
                f"memory://slack-shaped/{fixture.channel_id}/{fixture.thread_id}/"
                f"messages/{fixture.anchor_event_id}"
            ),
            attachments=ANCHOR_ATTACHMENTS,
        )
    )

    assert result.processing_outcome is ProcessingOutcome.ACCEPTED_ORIGIN
    assert result.origin is not None
    assert result.origin.subject_text == fixture.subject_text
    # Origin body is the intake message only — not a thread summary.
    assert result.origin.body_text == fixture.body_text
    assert "lol ship it friday" not in result.origin.body_text
    assert "order lunch" not in result.origin.body_text

    stored = world.service.get_task_origin(result.origin.object_id)
    assert stored is not None
    manifest = stored.conversation_context_manifest
    assert manifest

    by_relation: dict[str, list[ConversationContextManifestEntry]] = {}
    for entry in manifest:
        by_relation.setdefault(entry.relation, []).append(entry)

    assert by_relation["thread_boundary"][0].external_id == fixture.thread_id
    assert by_relation["parent_location"][0].external_id == fixture.channel_id

    preceding_ids = [entry.external_id for entry in by_relation["preceding"]]
    assert preceding_ids == list(fixture.preceding_message_ids)

    # Noise and relevant chatter are both retained as opaque refs.
    assert "S4821-02" in preceding_ids  # joke
    assert "S4821-04" in preceding_ids  # lunch tangent
    assert "S4821-03" in preceding_ids  # flaky-claim mention

    omission_ids = [entry.external_id for entry in by_relation["omission"]]
    assert fixture.omission_id in omission_ids
    assert any(entry.note == fixture.omission_note for entry in by_relation["omission"])

    anchors = by_relation["anchor"]
    assert len(anchors) == 1
    assert anchors[0].external_id == fixture.anchor_event_id
    assert anchors[0].kind == "message"

    attachment_ids = [
        entry.external_id for entry in manifest if entry.kind == "attachment"
    ]
    for attachment_id in fixture.preceding_attachment_ids:
        assert attachment_id in attachment_ids
    for attachment_id in fixture.anchor_attachment_ids:
        assert attachment_id in attachment_ids

    assert [entry.sequence for entry in manifest] == list(range(len(manifest)))
    relations = [entry.relation for entry in manifest]
    assert relations[0] == "thread_boundary"
    assert relations[1] == "parent_location"
    assert relations.index("anchor") > max(
        i for i, relation in enumerate(relations) if relation == "preceding"
    )
    for attachment_id in fixture.anchor_attachment_ids:
        assert relations.index("anchor") < next(
            i
            for i, entry in enumerate(manifest)
            if entry.kind == "attachment" and entry.external_id == attachment_id
        )

    # Replay must keep the same captured manifest even if adapter history clears.
    world.adapter._thread_history.clear()
    replay = world.orchestrator.handle_inbound(
        _payload(
            world,
            external_event_id=fixture.anchor_event_id,
            body_text=fixture.body_text,
            location_kind="thread",
            external_location_id=fixture.thread_id,
            location_locator=(
                f"memory://slack-shaped/{fixture.channel_id}/threads/{fixture.thread_id}"
            ),
            parent_location_kind="channel",
            parent_external_location_id=fixture.channel_id,
            parent_location_locator=(
                f"memory://slack-shaped/channels/{fixture.channel_id}"
            ),
            attachments=ANCHOR_ATTACHMENTS,
        )
    )
    assert replay.processing_outcome is ProcessingOutcome.DUPLICATE_REPLAY
    assert replay.origin is not None
    assert replay.origin.conversation_context_manifest == manifest


def test_messy_slack_thread_fixture_does_not_claim_semantic_selection() -> None:
    """Guardrail: fixture transcript noise is documentation, not selection input."""

    fixture = build_messy_slack_thread_fixture()
    noisy = {
        row["external_id"]
        for row in MESSY_SLACK_THREAD_TRANSCRIPT
        if "lol" in row["text"] or "lunch" in row["text"]
    }
    relevantish = {
        row["external_id"]
        for row in MESSY_SLACK_THREAD_TRANSCRIPT
        if "claim race" in row["text"] and row["role"] == "preceding"
    }
    assert noisy
    assert relevantish
    # Capture expectations keep both sets — no relevance filter in M2-018.
    assert noisy.issubset(set(fixture.preceding_message_ids))
    assert relevantish.issubset(set(fixture.preceding_message_ids))
