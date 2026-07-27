"""Replaceable collaboration adapter port."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from holodeck_governance.domain.collaboration.inbound import (
    NormalizedInboundEvent,
    VerifiedActorIdentity,
)
from holodeck_governance.domain.collaboration.outbound import OutboundCollaborationMessage


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
