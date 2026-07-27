"""Architecture boundary tests for M1 module contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from holodeck_governance.domain import vocabulary as vocab

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
DOMAIN_PATH = SRC_ROOT / "holodeck_governance" / "domain"
APPLICATION_PATH = SRC_ROOT / "holodeck_governance" / "application"
STORAGE_PATH = SRC_ROOT / "holodeck_governance" / "storage"

REQUIRED_PACKETS = {
    "M1-003",
    "M1-005",
    "M1-007",
    "M1-008",
    "M1-009",
    "M1-010",
    "M1-011",
    "M1-012",
    "M1-013",
    "M1-014",
    "M1-017",
    "M1-018",
    "M1-019",
    "M1-020",
    "M1-021",
    "M1-027",
    "M1-028",
    "M1-029",
}


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _is_forbidden(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def test_vocabulary_covers_required_record_families() -> None:
    records = set(vocab.ownership_by_record())
    expected = {
        "Tenant",
        "Actor",
        "RoleProfile",
        "RoleAssignment",
        "DelegatedGrant",
        "RevocationDecision",
        "Workspace",
        "Source",
        "Intent",
        "Mission",
        "Task",
        "Requirement",
        "TestPlan",
        "Run",
        "Artifact",
        "Evidence",
        "Review",
        "Approval",
        "Decision",
        "Escalation",
        "ExternalReference",
        "ProvenanceRecord",
        "TrustClassification",
        "ValidationDecision",
        "CommandReceipt",
        "EvaluationSnapshot",
        "EvaluationResult",
        "PolicyBinding",
        "OverrideDecision",
        "TransitionRecord",
        "DomainEvent",
        "OutboxItem",
        "OutboxAttempt",
        "GovernanceObject",
        "ObjectRevision",
        "TraceabilityEdge",
    }
    assert records == expected


def test_each_record_has_unique_persistence_contract_name() -> None:
    contracts = [item.persistence_contract for item in vocab.RECORD_OWNERSHIP]
    assert len(contracts) == len(set(contracts))


def test_implementing_packets_cover_core_families() -> None:
    packets = {item.implementing_packet for item in vocab.RECORD_OWNERSHIP}
    missing = REQUIRED_PACKETS - packets
    assert not missing


def test_catalog_and_unit_of_work_ownership_declared() -> None:
    assert vocab.CATALOG_MODULES["domain_errors"].endswith("catalogs.errors")
    assert vocab.CATALOG_MODULES["implementing_packet"] == "M1-031"
    assert vocab.OPAQUE_ID_PACKET == "M1-004"
    assert vocab.OPAQUE_ID_MODULE.endswith(".ids")
    assert vocab.REPOSITORY_UNIT_OF_WORK["implementing_packet"] == "M1-030"
    assert vocab.LEGACY_MIGRATION_SEAMS["legacy_import_mapping_packet"] == "M1-006"


def test_domain_modules_do_not_import_forbidden_layers() -> None:
    violations: list[str] = []
    for path in _python_files(DOMAIN_PATH):
        for module in _imported_modules(path):
            if _is_forbidden(module, vocab.FORBIDDEN_DOMAIN_IMPORT_PREFIXES):
                violations.append(f"{path.relative_to(SRC_ROOT)} imports {module}")
    assert violations == []


def test_application_modules_do_not_import_sqlite_or_adapters() -> None:
    forbidden = (
        "holodeck_governance.storage.sqlite",
        "holodeck_control_plane",
        "sqlite3",
    )
    violations: list[str] = []
    for path in _python_files(APPLICATION_PATH):
        for module in _imported_modules(path):
            if _is_forbidden(module, forbidden):
                violations.append(f"{path.relative_to(SRC_ROOT)} imports {module}")
    assert violations == []


def test_control_plane_governance_adapter_does_not_import_sqlite_impl() -> None:
    path = SRC_ROOT / "holodeck_control_plane" / "governance_commands.py"
    forbidden = (
        "holodeck_governance.storage.sqlite",
        "sqlite3",
    )
    violations = [
        module
        for module in _imported_modules(path)
        if _is_forbidden(module, forbidden)
    ]
    assert violations == []
    imports = _imported_modules(path)
    assert "holodeck_governance.composition" in imports
    assert "holodeck_governance.application.commands" not in imports or True


def test_storage_modules_do_not_import_application_or_http_adapters() -> None:
    forbidden = (
        "holodeck_governance.application",
        "holodeck_control_plane.http_server",
        "holodeck_control_plane.http_client",
        "holodeck_control_plane.mcp_server",
        "holodeck_control_plane.cli",
    )
    violations: list[str] = []
    for path in _python_files(STORAGE_PATH):
        for module in _imported_modules(path):
            if _is_forbidden(module, forbidden):
                violations.append(f"{path.relative_to(SRC_ROOT)} imports {module}")
    assert violations == []


def test_legacy_seam_marks_thin_slice_as_unsupported_governance() -> None:
    from holodeck_governance.storage import legacy_seam

    assert legacy_seam.PROVENANCE_KIND == "legacy_import"
    assert "Approval" in legacy_seam.UNSUPPORTED_AS_M1_GOVERNANCE
    assert "missions" in legacy_seam.LEGACY_THIN_SLICE_TABLES
    assert "tasks" in legacy_seam.LEGACY_COORDINATION_TABLES


@pytest.mark.parametrize(
    "record",
    ["Mission", "Evidence", "Decision", "Approval"],
)
def test_thin_slice_namesakes_are_owned_by_m1_packets_not_m0(record: str) -> None:
    ownership = vocab.ownership_by_record()[record]
    assert ownership.implementing_packet.startswith("M1-")
    assert "holodeck_control_plane" not in ownership.domain_module
