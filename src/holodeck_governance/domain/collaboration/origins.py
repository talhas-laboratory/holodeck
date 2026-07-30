"""Durable task-origin records for explicit collaboration intake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from holodeck_governance.domain.collaboration.inbound import AttachmentRef
from holodeck_governance.domain.collaboration.types import (
    AdapterMetadata,
    LocationKind,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id
from holodeck_governance.domain.records._common import require_utc

_MANIFEST_KINDS = frozenset({"message", "attachment", "omission"})
_MANIFEST_RELATIONS = frozenset(
    {
        "anchor",
        "preceding",
        "attachment",
        "thread_boundary",
        "omission",
        "parent_location",
    }
)


def _freeze_metadata(metadata: Mapping[str, str] | None) -> Mapping[str, str]:
    if metadata is None:
        return {}
    return {str(key): str(value) for key, value in metadata.items()}


@dataclass(frozen=True, slots=True)
class ConversationContextManifestEntry:
    """Opaque message, attachment, or omission reference from intake context.

    Entries are reconstitution pointers into the collaboration provider — not
    Holodeck workspace ids and not mission authority.
    """

    kind: str
    external_id: str
    locator: str = ""
    relation: str = "preceding"
    sequence: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _MANIFEST_KINDS:
            raise MalformedCommandError(
                "conversation context entry kind must be message, "
                "attachment, or omission"
            )
        if self.relation not in _MANIFEST_RELATIONS:
            raise MalformedCommandError(
                "conversation context entry relation is invalid"
            )
        if not self.external_id.strip():
            raise MalformedCommandError("external_id is required")
        if self.sequence < 0:
            raise MalformedCommandError("sequence must be >= 0")


@dataclass(frozen=True, slots=True)
class TaskOrigin:
    """Durable origin of governed work initiated from collaboration intake.

    A task origin is not a mission, run, approval, or acceptance decision.
    """

    object_id: str
    tenant_id: str
    actor_id: str
    inbound_receipt_id: str
    source_reference_id: str
    provider: str
    external_event_id: str
    subject_text: str
    body_text: str
    location_kind: LocationKind
    location_reference_id: str
    created_at: datetime
    created_by_actor_id: str
    mapping_id: str
    endpoint_id: str | None = None
    parent_location_reference_id: str | None = None
    adapter_metadata: AdapterMetadata = field(default_factory=dict)
    conversation_context_manifest: tuple[ConversationContextManifestEntry, ...] = ()
    schema_version: str = "m2.task_origin.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("object_id", self.object_id),
            ("tenant_id", self.tenant_id),
            ("actor_id", self.actor_id),
            ("inbound_receipt_id", self.inbound_receipt_id),
            ("source_reference_id", self.source_reference_id),
            ("location_reference_id", self.location_reference_id),
            ("created_by_actor_id", self.created_by_actor_id),
            ("mapping_id", self.mapping_id),
        ):
            require_opaque_id(value, name)
        if self.endpoint_id is not None:
            require_opaque_id(self.endpoint_id, "endpoint_id")
        if self.parent_location_reference_id is not None:
            require_opaque_id(
                self.parent_location_reference_id, "parent_location_reference_id"
            )
        require_utc(self.created_at, "created_at")
        if not self.provider.strip():
            raise MalformedCommandError("provider is required")
        if not self.external_event_id.strip():
            raise MalformedCommandError("external_event_id is required")
        if not self.subject_text.strip():
            raise MalformedCommandError("subject_text is required")
        if not self.body_text.strip():
            raise MalformedCommandError("body_text is required")
        object.__setattr__(self, "adapter_metadata", _freeze_metadata(self.adapter_metadata))
        object.__setattr__(
            self,
            "conversation_context_manifest",
            tuple(self.conversation_context_manifest),
        )


def task_origin_dedupe_key(origin: TaskOrigin) -> tuple[str, str, str]:
    return (origin.tenant_id, origin.provider, origin.external_event_id)


def build_conversation_context_manifest(
    *,
    anchor_external_event_id: str,
    anchor_locator: str,
    location_external_id: str,
    location_locator: str,
    location_kind: str,
    thread_entries: tuple[ConversationContextManifestEntry, ...] = (),
    attachments: tuple[AttachmentRef, ...] = (),
    parent_location_external_id: str | None = None,
    parent_location_locator: str = "",
) -> tuple[ConversationContextManifestEntry, ...]:
    """Merge thread fetch, location boundary, anchor, and attachments.

    Deterministic order: thread_boundary → parent_location → preceding (by
    sequence) → anchor → attachments → omissions. Dedupes by (kind, external_id).
    """

    if not anchor_external_event_id.strip():
        raise MalformedCommandError("anchor_external_event_id is required")
    if not location_external_id.strip():
        raise MalformedCommandError("location_external_id is required")
    if not location_kind.strip():
        raise MalformedCommandError("location_kind is required")

    ordered: list[ConversationContextManifestEntry] = [
        ConversationContextManifestEntry(
            kind="message",
            external_id=location_external_id,
            locator=location_locator,
            relation="thread_boundary",
            sequence=0,
            note=location_kind,
        )
    ]
    if parent_location_external_id is not None and parent_location_external_id.strip():
        ordered.append(
            ConversationContextManifestEntry(
                kind="message",
                external_id=parent_location_external_id,
                locator=parent_location_locator,
                relation="parent_location",
                sequence=0,
            )
        )

    preceding = sorted(
        (
            entry
            for entry in thread_entries
            if not (
                entry.kind == "message"
                and entry.external_id == anchor_external_event_id
            )
            and entry.relation != "thread_boundary"
            and entry.relation != "parent_location"
            and entry.relation != "anchor"
        ),
        key=lambda entry: (entry.sequence, entry.kind, entry.external_id),
    )
    ordered.extend(
        ConversationContextManifestEntry(
            kind=entry.kind,
            external_id=entry.external_id,
            locator=entry.locator,
            relation=(
                entry.relation
                if entry.relation in {"preceding", "attachment", "omission"}
                else "preceding"
            ),
            sequence=entry.sequence,
            note=entry.note,
        )
        for entry in preceding
    )
    ordered.append(
        ConversationContextManifestEntry(
            kind="message",
            external_id=anchor_external_event_id,
            locator=anchor_locator,
            relation="anchor",
            sequence=0,
        )
    )
    for attachment in attachments:
        ordered.append(
            ConversationContextManifestEntry(
                kind="attachment",
                external_id=attachment.external_attachment.external_object_id,
                locator=attachment.external_attachment.locator,
                relation="attachment",
                sequence=0,
            )
        )

    deduped: list[ConversationContextManifestEntry] = []
    seen: set[tuple[str, str]] = set()
    for entry in ordered:
        key = (entry.kind, entry.external_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    return tuple(
        ConversationContextManifestEntry(
            kind=entry.kind,
            external_id=entry.external_id,
            locator=entry.locator,
            relation=entry.relation,
            sequence=index,
            note=entry.note,
        )
        for index, entry in enumerate(deduped)
    )


def conversation_context_manifest_to_jsonable(
    manifest: tuple[ConversationContextManifestEntry, ...],
) -> list[dict[str, object]]:
    return [
        {
            "kind": entry.kind,
            "external_id": entry.external_id,
            "locator": entry.locator,
            "relation": entry.relation,
            "sequence": entry.sequence,
            "note": entry.note,
        }
        for entry in manifest
    ]


def conversation_context_manifest_from_jsonable(
    raw: object,
) -> tuple[ConversationContextManifestEntry, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise MalformedCommandError("conversation_context_manifest must be a list")
    entries: list[ConversationContextManifestEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            raise MalformedCommandError(
                "conversation_context_manifest entries must be objects"
            )
        sequence_raw = item.get("sequence", 0)
        try:
            sequence = int(sequence_raw)
        except (TypeError, ValueError) as exc:
            raise MalformedCommandError(
                "conversation_context_manifest sequence must be an int"
            ) from exc
        kind = str(item.get("kind", ""))
        relation = str(item.get("relation") or _default_relation(kind))
        entries.append(
            ConversationContextManifestEntry(
                kind=kind,
                external_id=str(item.get("external_id", "")),
                locator=str(item.get("locator", "")),
                relation=relation,
                sequence=sequence,
                note=str(item.get("note", "")),
            )
        )
    return tuple(entries)


def _default_relation(kind: str) -> str:
    if kind == "attachment":
        return "attachment"
    if kind == "omission":
        return "omission"
    return "preceding"
