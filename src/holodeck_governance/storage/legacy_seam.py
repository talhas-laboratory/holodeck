"""Explicit M0 → M1 additive migration seam.

Legacy coordination and thin-slice tables are import inputs. They are never
silently reinterpreted as M1 approvals, evidence, policies, evaluations, or
decisions. Mapping contracts land in M1-006; production migration in M1-023.
"""

from __future__ import annotations

from holodeck_governance.domain.legacy_mapping import (
    PROVENANCE_KIND,
    UNSUPPORTED_AS_M1_GOVERNANCE,
)

LEGACY_COORDINATION_TABLES: tuple[str, ...] = (
    "workspaces",
    "tasks",
    "runs",
    "claims",
)

LEGACY_THIN_SLICE_TABLES: tuple[str, ...] = (
    "workspace_sources",
    "curator_proposals",
    "missions",
    "mission_evidence",
    "acceptance_decisions",
)

__all__ = [
    "LEGACY_COORDINATION_TABLES",
    "LEGACY_THIN_SLICE_TABLES",
    "PROVENANCE_KIND",
    "UNSUPPORTED_AS_M1_GOVERNANCE",
]
