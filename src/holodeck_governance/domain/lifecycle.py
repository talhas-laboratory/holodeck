"""Versioned task/run transition definitions (M1-013 / GS-006)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from holodeck_governance.domain.errors import InvalidTransitionError, MalformedCommandError


TASK_DEFINITION_VERSION: Final = "m1.task_lifecycle.v1"
RUN_DEFINITION_VERSION: Final = "m1.run_lifecycle.v1"

TASK_STATES: Final[frozenset[str]] = frozenset(
    {"draft", "ready", "active", "submitted", "accepted", "blocked", "cancelled"}
)
RUN_STATES: Final[frozenset[str]] = frozenset(
    {"created", "active", "completed", "failed", "interrupted", "cancelled"}
)

TASK_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"ready", "blocked", "cancelled"}),
    "ready": frozenset({"active", "blocked", "cancelled"}),
    "active": frozenset({"submitted", "blocked", "cancelled"}),
    "submitted": frozenset({"accepted", "active", "blocked", "cancelled"}),
    "blocked": frozenset({"draft", "ready", "active", "submitted", "cancelled"}),
    "accepted": frozenset(),
    "cancelled": frozenset(),
}

RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "created": frozenset({"active", "cancelled"}),
    "active": frozenset({"completed", "failed", "interrupted", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "interrupted": frozenset({"active", "cancelled"}),
    "cancelled": frozenset(),
}


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    transition_id: str
    tenant_id: str
    subject_object_id: str
    subject_kind: str
    from_state: str
    to_state: str
    definition_version: str
    actor_id: str
    created_at: str


def validate_task_transition(current: str, target: str) -> str:
    if current not in TASK_STATES:
        raise MalformedCommandError(f"unknown task state: {current}")
    if target not in TASK_STATES:
        raise MalformedCommandError(f"unknown task state: {target}")
    if target not in TASK_TRANSITIONS[current]:
        raise InvalidTransitionError(f"illegal task transition: {current} -> {target}")
    return TASK_DEFINITION_VERSION


def validate_run_transition(current: str, target: str) -> str:
    if current not in RUN_STATES:
        raise MalformedCommandError(f"unknown run state: {current}")
    if target not in RUN_STATES:
        raise MalformedCommandError(f"unknown run state: {target}")
    if target not in RUN_TRANSITIONS[current]:
        raise InvalidTransitionError(f"illegal run transition: {current} -> {target}")
    return RUN_DEFINITION_VERSION
