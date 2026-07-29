"""Replaceable collaboration adapter port."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from holodeck_governance.domain.collaboration.inbound import (
    NormalizedInboundEvent,
    VerifiedActorIdentity,
)
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage
from holodeck_governance.domain.collaboration.origins import (
    ConversationContextManifestEntry,
)
from holodeck_governance.domain.collaboration.types import VerificationResult
from holodeck_governance.domain.errors import GovernanceError


class CollaborationAdapterAuthError(GovernanceError):
    """Adapter-local authentication failure.

    Refuses a trusted tenant event. Does not create a Holodeck inbound receipt
    (CIS-001).
    """

    def __init__(
        self,
        message: str,
        *,
        verification_result: VerificationResult,
    ) -> None:
        super().__init__(message)
        self.verification_result = verification_result


class CollaborationAdapter(Protocol):
    """Provider adapter boundary.

    Implementations may use provider SDKs internally. They must return only
    provider-neutral Holodeck collaboration contracts to the domain/application
    layers.
    """

    def normalize_inbound(
        self, raw_provider_payload: Mapping[str, Any]
    ) -> NormalizedInboundEvent:
        """Translate a provider payload into a normalized inbound event."""

    def verify_and_map_actor(
        self, event: NormalizedInboundEvent
    ) -> VerifiedActorIdentity:
        """Verify signature/membership and map to a Holodeck actor."""

    def publish_outbound(self, message: OutboundCollaborationMessage) -> Mapping[str, str]:
        """Deliver one outbox-backed status message to the provider.

        The returned mapping is adapter acknowledgement metadata only. It is not
        proof of downstream Holodeck processing.
        """

    def fetch_thread_context(
        self,
        *,
        tenant_id: str,
        location_kind: str,
        external_location_id: str,
        anchor_external_event_id: str | None = None,
    ) -> tuple[ConversationContextManifestEntry, ...]:
        """Optional preceding thread context for origin manifests (M2-018).

        Returns opaque message/attachment/omission entries for reconstitution.
        May return an empty tuple when the provider has no durable history.
        Partial retrieval should record omission entries rather than raising
        when the adapter can still produce a useful partial manifest.
        """
