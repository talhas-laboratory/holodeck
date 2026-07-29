"""Provider-neutral in-memory collaboration adapter harness (M2-008).

Implements CollaborationAdapter without a live provider SDK. Used by tests and
as the reference shape for Buzz (M2-009). Holodeck still owns receipts, origins,
and the durable outbox; this adapter only normalizes, verifies/maps, and
delivers outbound acknowledgements into a local mailbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, MutableMapping

from holodeck_governance.domain.collaboration.adapter import CollaborationAdapterAuthError
from holodeck_governance.domain.collaboration.inbound import (
    AttachmentRef,
    ConversationLocation,
    NormalizedInboundEvent,
    VerifiedActorIdentity,
)
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage
from holodeck_governance.domain.collaboration.types import LocationKind, VerificationResult
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import generate_uuidv7, require_opaque_id
from holodeck_governance.domain.provenance.external_reference import ExternalReference

MEMORY_PROVIDER = "memory"
_VALID_SIGNATURE = "ok"


@dataclass(frozen=True, slots=True)
class MemoryExternalActor:
    """Configured external actor → Holodeck actor mapping for the harness."""

    external_actor_id: str
    tenant_id: str
    actor_id: str
    identity_locator: str
    display_name: str = ""

    def __post_init__(self) -> None:
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.actor_id, "actor_id")
        if not self.external_actor_id.strip():
            raise MalformedCommandError("external_actor_id is required")
        if not self.identity_locator.strip():
            raise MalformedCommandError("identity_locator is required")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class InMemoryCollaborationAdapter:
    """In-memory CollaborationAdapter with a deterministic outbound mailbox."""

    created_by_actor_id: str
    clock: Callable[[], datetime] = field(default=_utc_now)
    id_factory: Callable[[], str] = field(default=generate_uuidv7)
    _actors: MutableMapping[str, MemoryExternalActor] = field(default_factory=dict)
    _published: list[OutboundCollaborationMessage] = field(default_factory=list)
    _acks_by_idempotency_key: MutableMapping[str, dict[str, str]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        require_opaque_id(self.created_by_actor_id, "created_by_actor_id")

    @property
    def provider(self) -> str:
        return MEMORY_PROVIDER

    def register_actor(self, actor: MemoryExternalActor) -> None:
        self._actors[actor.external_actor_id] = actor

    @property
    def published_messages(self) -> tuple[OutboundCollaborationMessage, ...]:
        return tuple(self._published)

    def normalize_inbound(
        self, raw_provider_payload: Mapping[str, Any]
    ) -> NormalizedInboundEvent:
        """Translate a memory-provider dict into a normalized inbound event.

        Invalid or missing signatures refuse normalization (CIS-001).
        """

        if not isinstance(raw_provider_payload, Mapping):
            raise MalformedCommandError("memory payload must be a mapping")

        signature = str(raw_provider_payload.get("signature", "")).strip()
        if not signature:
            raise CollaborationAdapterAuthError(
                "memory inbound event is unsigned",
                verification_result=VerificationResult.UNSIGNED,
            )
        if signature != _VALID_SIGNATURE:
            raise CollaborationAdapterAuthError(
                "memory inbound event signature verification failed",
                verification_result=VerificationResult.FAILED,
            )

        tenant_id = _require_str(raw_provider_payload, "tenant_id")
        external_event_id = _require_str(raw_provider_payload, "external_event_id")
        external_actor_id = _require_str(raw_provider_payload, "external_actor_id")
        body_text = str(raw_provider_payload.get("body_text", ""))
        location_kind = LocationKind(
            _require_str(raw_provider_payload, "location_kind")
        )
        external_location_id = _require_str(raw_provider_payload, "external_location_id")
        location_locator = str(
            raw_provider_payload.get("location_locator")
            or f"memory://locations/{external_location_id}"
        )
        occurred_at = _parse_datetime(
            raw_provider_payload.get("occurred_at"), field_name="occurred_at"
        )
        received_at = self.clock()
        endpoint_id = raw_provider_payload.get("endpoint_id")
        if endpoint_id is not None:
            endpoint_id = str(endpoint_id)

        binding = self._actors.get(external_actor_id)
        if binding is None:
            raise CollaborationAdapterAuthError(
                f"unknown memory external actor {external_actor_id}",
                verification_result=VerificationResult.FAILED,
            )
        if binding.tenant_id != tenant_id:
            raise CollaborationAdapterAuthError(
                "memory external actor tenant mismatch",
                verification_result=VerificationResult.FAILED,
            )

        identity_ref = ExternalReference(
            reference_id=self.id_factory(),
            tenant_id=tenant_id,
            provider=MEMORY_PROVIDER,
            object_type="external_actor",
            external_object_id=external_actor_id,
            locator=binding.identity_locator,
            observed_at=occurred_at,
            created_at=received_at,
            created_by_actor_id=self.created_by_actor_id,
        )
        verified_actor = VerifiedActorIdentity(
            tenant_id=tenant_id,
            actor_id=binding.actor_id,
            external_identity=identity_ref,
            verification_result=VerificationResult.VERIFIED,
            verified_at=received_at,
            adapter_metadata={
                "signature": signature,
                "external_actor_id": external_actor_id,
                **(
                    {"display_name": binding.display_name}
                    if binding.display_name
                    else {}
                ),
            },
        )

        location_ref = ExternalReference(
            reference_id=self.id_factory(),
            tenant_id=tenant_id,
            provider=MEMORY_PROVIDER,
            object_type=location_kind.value,
            external_object_id=external_location_id,
            locator=location_locator,
            observed_at=occurred_at,
            created_at=received_at,
            created_by_actor_id=self.created_by_actor_id,
        )
        parent_ref = None
        parent_kind_raw = raw_provider_payload.get("parent_location_kind")
        parent_external_id = raw_provider_payload.get("parent_external_location_id")
        if parent_kind_raw is not None or parent_external_id is not None:
            parent_kind = LocationKind(_require_str(raw_provider_payload, "parent_location_kind"))
            parent_id = _require_str(raw_provider_payload, "parent_external_location_id")
            parent_locator = str(
                raw_provider_payload.get("parent_location_locator")
                or f"memory://locations/{parent_id}"
            )
            parent_ref = ExternalReference(
                reference_id=self.id_factory(),
                tenant_id=tenant_id,
                provider=MEMORY_PROVIDER,
                object_type=parent_kind.value,
                external_object_id=parent_id,
                locator=parent_locator,
                observed_at=occurred_at,
                created_at=received_at,
                created_by_actor_id=self.created_by_actor_id,
            )

        location = ConversationLocation(
            location_kind=location_kind,
            external_location=location_ref,
            parent_external_location=parent_ref,
            endpoint_id=None if endpoint_id is None else str(endpoint_id),
            adapter_metadata={"provider_path": location_locator},
        )

        source_ref = ExternalReference(
            reference_id=self.id_factory(),
            tenant_id=tenant_id,
            provider=MEMORY_PROVIDER,
            object_type="collaboration_event",
            external_object_id=external_event_id,
            locator=str(
                raw_provider_payload.get("event_locator")
                or f"memory://events/{external_event_id}"
            ),
            observed_at=occurred_at,
            created_at=received_at,
            created_by_actor_id=self.created_by_actor_id,
        )

        attachments: list[AttachmentRef] = []
        for item in raw_provider_payload.get("attachments") or ():
            if not isinstance(item, Mapping):
                raise MalformedCommandError("attachment entries must be mappings")
            attachment_external_id = _require_str(item, "external_attachment_id")
            content_type = _require_str(item, "content_type")
            attachment_ref = ExternalReference(
                reference_id=self.id_factory(),
                tenant_id=tenant_id,
                provider=MEMORY_PROVIDER,
                object_type="attachment",
                external_object_id=attachment_external_id,
                locator=str(
                    item.get("locator") or f"memory://files/{attachment_external_id}"
                ),
                observed_at=occurred_at,
                created_at=received_at,
                created_by_actor_id=self.created_by_actor_id,
                content_hash=(
                    None
                    if item.get("content_hash") is None
                    else str(item["content_hash"])
                ),
            )
            attachments.append(
                AttachmentRef(
                    attachment_id=self.id_factory(),
                    external_attachment=attachment_ref,
                    content_type=content_type,
                    content_hash=attachment_ref.content_hash,
                    byte_size=(
                        None if item.get("byte_size") is None else int(item["byte_size"])
                    ),
                    adapter_metadata={
                        str(k): str(v)
                        for k, v in item.items()
                        if k
                        not in {
                            "external_attachment_id",
                            "content_type",
                            "locator",
                            "content_hash",
                            "byte_size",
                        }
                    },
                )
            )

        metadata = {
            str(k): str(v)
            for k, v in raw_provider_payload.items()
            if k
            not in {
                "tenant_id",
                "external_event_id",
                "external_actor_id",
                "body_text",
                "location_kind",
                "external_location_id",
                "location_locator",
                "parent_location_kind",
                "parent_external_location_id",
                "parent_location_locator",
                "signature",
                "occurred_at",
                "endpoint_id",
                "event_locator",
                "attachments",
            }
            and not isinstance(v, (dict, list))
        }

        return NormalizedInboundEvent(
            inbound_event_id=self.id_factory(),
            tenant_id=tenant_id,
            provider=MEMORY_PROVIDER,
            external_event_id=external_event_id,
            occurred_at=occurred_at,
            received_at=received_at,
            verified_actor=verified_actor,
            location=location,
            body_text=body_text,
            source_reference=source_ref,
            attachments=tuple(attachments),
            adapter_metadata=metadata,
        )

    def verify_and_map_actor(
        self, event: NormalizedInboundEvent
    ) -> VerifiedActorIdentity:
        """Confirm the event's mapped actor is still registered for this harness."""

        if event.provider != MEMORY_PROVIDER:
            raise MalformedCommandError(
                f"memory adapter cannot verify provider {event.provider}"
            )
        external_actor_id = event.verified_actor.external_identity.external_object_id
        binding = self._actors.get(external_actor_id)
        if binding is None:
            raise CollaborationAdapterAuthError(
                f"unknown memory external actor {external_actor_id}",
                verification_result=VerificationResult.FAILED,
            )
        if binding.tenant_id != event.tenant_id or binding.actor_id != event.verified_actor.actor_id:
            raise CollaborationAdapterAuthError(
                "memory actor mapping mismatch",
                verification_result=VerificationResult.FAILED,
            )
        if event.verified_actor.verification_result is not VerificationResult.VERIFIED:
            raise CollaborationAdapterAuthError(
                "memory inbound event is not verified",
                verification_result=event.verified_actor.verification_result,
            )
        return event.verified_actor

    def publish_outbound(self, message: OutboundCollaborationMessage) -> Mapping[str, str]:
        """Deliver one outbox-backed status message into the local mailbox.

        Republishing the same idempotency_key returns the prior acknowledgement
        without duplicating the semantic message.
        """

        if message.provider != MEMORY_PROVIDER:
            raise MalformedCommandError(
                f"memory adapter cannot publish provider {message.provider}"
            )
        existing = self._acks_by_idempotency_key.get(message.idempotency_key)
        if existing is not None:
            return dict(existing)

        delivery_id = self.id_factory()
        self._published.append(message)
        ack = {
            "status": "delivered",
            "provider": MEMORY_PROVIDER,
            "idempotency_key": message.idempotency_key,
            "delivery_id": delivery_id,
            "message_id": message.message_id,
        }
        self._acks_by_idempotency_key[message.idempotency_key] = ack
        return dict(ack)


def _require_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or not str(value).strip():
        raise MalformedCommandError(f"memory payload field {key} is required")
    return str(value)


def _parse_datetime(value: Any, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise MalformedCommandError(f"{field_name} must be timezone-aware UTC")
        return value
    if value is None or not str(value).strip():
        raise MalformedCommandError(f"{field_name} is required")
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise MalformedCommandError(f"{field_name} must be timezone-aware UTC")
    return parsed.astimezone(UTC)
