"""Explicit intake-command grammar and policy inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from holodeck_governance.domain.collaboration.inbound import ConversationLocation
from holodeck_governance.domain.collaboration.types import (
    INTAKE_ADDRESS_TOKEN,
    INTAKE_VERB_WORK,
)
from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.ids import require_opaque_id

_INTAKE_PATTERN = re.compile(
    rf"^\s*[@/]{INTAKE_ADDRESS_TOKEN}\s+(?P<verb>[A-Za-z]+)\s*:?\s*(?P<subject>.*?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class IntakeCommand:
    raw_text: str
    verb: str | None
    subject_text: str | None
    is_explicit_intake: bool

    def __post_init__(self) -> None:
        if self.is_explicit_intake:
            if self.verb != INTAKE_VERB_WORK:
                raise MalformedCommandError("explicit intake verb must be work")
            if self.subject_text is None or not self.subject_text.strip():
                raise MalformedCommandError("explicit intake requires subject_text")


@dataclass(frozen=True, slots=True)
class IntakePolicyInputs:
    tenant_id: str
    actor_id: str
    location: ConversationLocation
    required_capability: str = "collaboration.intake"
    automation_level: str = "assisted"
    allow_unbound_location: bool = False
    risk_class: str = "standard"
    endpoint_id: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.tenant_id, "tenant_id")
        require_opaque_id(self.actor_id, "actor_id")
        if self.endpoint_id is not None:
            require_opaque_id(self.endpoint_id, "endpoint_id")
        if self.automation_level not in {"manual", "assisted", "automatic"}:
            raise MalformedCommandError("automation_level invalid")
        if not self.required_capability.strip():
            raise MalformedCommandError("required_capability is required")
        if not self.risk_class.strip():
            raise MalformedCommandError("risk_class is required")


def parse_intake_command(raw_text: str) -> IntakeCommand:
    """Parse provider-normalized text into an intake command decision."""

    text = raw_text if isinstance(raw_text, str) else ""
    match = _INTAKE_PATTERN.match(text)
    if match is None:
        return IntakeCommand(
            raw_text=text,
            verb=None,
            subject_text=None,
            is_explicit_intake=False,
        )
    verb = match.group("verb").lower()
    subject = match.group("subject")
    if verb != INTAKE_VERB_WORK:
        return IntakeCommand(
            raw_text=text,
            verb=verb,
            subject_text=subject or None,
            is_explicit_intake=False,
        )
    if subject is None or not subject.strip():
        return IntakeCommand(
            raw_text=text,
            verb=verb,
            subject_text="",
            is_explicit_intake=False,
        )
    return IntakeCommand(
        raw_text=text,
        verb=verb,
        subject_text=subject.strip(),
        is_explicit_intake=True,
    )
