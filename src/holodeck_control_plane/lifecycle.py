from __future__ import annotations

from holodeck_control_plane.errors import ValidationError

TASK_STATUSES = frozenset(
    {"backlog", "ready", "in-progress", "review", "blocked", "done", "cancelled"}
)
RUN_STATUSES = frozenset({"active", "completed", "failed", "cancelled"})
RUN_TERMINALS = frozenset({"completed", "failed", "cancelled"})
TASK_TERMINALS = frozenset({"done", "cancelled"})

TASK_TRANSITIONS: dict[str, frozenset[str]] = {
    "backlog": frozenset({"ready", "blocked", "cancelled"}),
    "ready": frozenset({"backlog", "in-progress", "blocked", "cancelled"}),
    "in-progress": frozenset({"ready", "review", "blocked", "cancelled"}),
    "review": frozenset({"in-progress", "done", "blocked", "cancelled"}),
    "blocked": frozenset({"backlog", "ready", "in-progress", "review", "cancelled"}),
    "done": frozenset(),
    "cancelled": frozenset(),
}

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": RUN_TERMINALS,
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


def validate_task_status(status: str) -> str:
    value = status.strip()
    if value not in TASK_STATUSES:
        raise ValidationError(f"unsupported task status: {value}")
    return value


def validate_run_status(status: str) -> str:
    value = status.strip()
    if value not in RUN_STATUSES:
        raise ValidationError(f"unsupported run status: {value}")
    return value


def validate_task_transition(current: str, next_status: str) -> None:
    current_status = validate_task_status(current)
    target = validate_task_status(next_status)
    if target not in TASK_TRANSITIONS[current_status]:
        raise ValidationError(f"illegal task transition: {current_status} -> {target}")


def validate_run_transition(current: str, next_status: str) -> None:
    current_status = validate_run_status(current)
    target = validate_run_status(next_status)
    if target not in RUN_TRANSITIONS[current_status]:
        raise ValidationError(f"illegal run transition: {current_status} -> {target}")


def validate_task_can_start_run(task_status: str) -> None:
    status = validate_task_status(task_status)
    if status in TASK_TERMINALS:
        raise ValidationError(f"cannot begin run for task in status {status}")


def validate_run_completion_status(status: str) -> str:
    value = validate_run_status(status)
    if value not in RUN_TERMINALS:
        raise ValidationError(f"run completion status must be terminal: {value}")
    return value
