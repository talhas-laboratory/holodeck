"""Legacy lifecycle import mapping contract (M1-006).

Maps M0 statuses to M1 lifecycle labels as `legacy_import` facts only.
Does not invent M1 transitions, authority, approvals, evidence, or decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.errors import GovernanceError

Disposition = Literal["map", "unsupported"]

PROVENANCE_KIND = "legacy_import"
UNSUPPORTED_AS_M1_GOVERNANCE: Final[tuple[str, ...]] = (
    "Approval",
    "Evidence",
    "PolicyBinding",
    "EvaluationSnapshot",
    "EvaluationResult",
    "Decision",
    "DelegatedGrant",
    "RoleAssignment",
)


@dataclass(frozen=True, slots=True)
class LegacyStatusMapping:
    surface: str
    legacy_value: str
    disposition: Disposition
    m1_value: str | None
    notes: str = ""


class UnsupportedLegacyMappingError(GovernanceError):
    code = DomainErrorCode.UNSUPPORTED_LEGACY_MAPPING


TASK_STATUS_MAP: Final[tuple[LegacyStatusMapping, ...]] = (
    LegacyStatusMapping("task", "backlog", "map", "draft"),
    LegacyStatusMapping("task", "ready", "map", "ready"),
    LegacyStatusMapping("task", "in-progress", "map", "active"),
    LegacyStatusMapping("task", "review", "map", "submitted"),
    LegacyStatusMapping("task", "blocked", "map", "blocked"),
    LegacyStatusMapping("task", "done", "map", "accepted"),
    LegacyStatusMapping("task", "cancelled", "map", "cancelled"),
)

RUN_STATUS_MAP: Final[tuple[LegacyStatusMapping, ...]] = (
    LegacyStatusMapping("run", "active", "map", "active"),
    LegacyStatusMapping("run", "completed", "map", "completed"),
    LegacyStatusMapping("run", "failed", "map", "failed"),
    LegacyStatusMapping("run", "cancelled", "map", "cancelled"),
)

CLAIM_STATUS_MAP: Final[tuple[LegacyStatusMapping, ...]] = (
    LegacyStatusMapping(
        "claim",
        "active",
        "map",
        "active",
        notes="Coordination fact only; no M1 authority semantics.",
    ),
    LegacyStatusMapping(
        "claim",
        "released",
        "map",
        "released",
        notes="Coordination fact only; no M1 authority semantics.",
    ),
)

THIN_SLICE_UNSUPPORTED: Final[tuple[LegacyStatusMapping, ...]] = (
    LegacyStatusMapping(
        "thin_slice",
        "missions",
        "unsupported",
        None,
        notes="Not an M1 Mission/Approval/Decision record.",
    ),
    LegacyStatusMapping(
        "thin_slice",
        "mission_evidence",
        "unsupported",
        None,
        notes="Not an M1 Evidence record.",
    ),
    LegacyStatusMapping(
        "thin_slice",
        "acceptance_decisions",
        "unsupported",
        None,
        notes="Not an M1 Decision/Approval record.",
    ),
    LegacyStatusMapping(
        "thin_slice",
        "curator_proposals",
        "unsupported",
        None,
        notes="Not an M1 PolicyBinding or Evaluation.",
    ),
)

ALL_MAPPINGS: Final[tuple[LegacyStatusMapping, ...]] = (
    TASK_STATUS_MAP + RUN_STATUS_MAP + CLAIM_STATUS_MAP + THIN_SLICE_UNSUPPORTED
)


def map_legacy_status(surface: str, legacy_value: str) -> LegacyStatusMapping:
    for item in ALL_MAPPINGS:
        if item.surface == surface and item.legacy_value == legacy_value:
            if item.disposition == "unsupported":
                raise UnsupportedLegacyMappingError(
                    f"legacy {surface}:{legacy_value} is unsupported as M1 governance"
                )
            return item
    raise UnsupportedLegacyMappingError(
        f"unknown legacy status {surface}:{legacy_value}"
    )


def dry_run_mapping(rows: list[tuple[str, str]]) -> list[dict[str, str | None]]:
    """Deterministic dry-run used by golden fixtures (GS-014 support)."""

    results: list[dict[str, str | None]] = []
    for surface, value in rows:
        try:
            mapped = map_legacy_status(surface, value)
            results.append(
                {
                    "surface": surface,
                    "legacy_value": value,
                    "disposition": mapped.disposition,
                    "m1_value": mapped.m1_value,
                    "provenance_kind": PROVENANCE_KIND,
                }
            )
        except UnsupportedLegacyMappingError as exc:
            results.append(
                {
                    "surface": surface,
                    "legacy_value": value,
                    "disposition": "unsupported",
                    "m1_value": None,
                    "provenance_kind": PROVENANCE_KIND,
                    "error_code": exc.code.value,
                }
            )
    return results


def asserts_no_fabricated_authority() -> tuple[str, ...]:
    return UNSUPPORTED_AS_M1_GOVERNANCE
