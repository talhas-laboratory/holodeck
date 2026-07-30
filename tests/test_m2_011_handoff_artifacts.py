"""M2-011 smoke: published handoff artifacts exist with required sections."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def _read(name: str) -> str:
    path = ARTIFACTS / name
    assert path.is_file(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_m2_011_contracts_index_has_required_sections() -> None:
    text = _read("m2-contracts-index.md")
    for needle in (
        "# M2 contracts index",
        "Collaboration intake boundary",
        "Buzz adapter (M2-009)",
        "gated",
        "Graph SQLite persistence",
        "Bounded queries + sentinels",
        "Verified commit:",
    ):
        assert needle in text, f"missing section/marker: {needle!r}"


def test_m2_011_consolidated_evidence_has_required_sections() -> None:
    text = _read("m2-consolidated-acceptance-evidence.md")
    for needle in (
        "# M2 consolidated acceptance evidence",
        "M2-010",
        "M2-017",
        "M2-026",
        "Residual risks",
        "Schema version",
        "v24",
    ):
        assert needle in text, f"missing section/marker: {needle!r}"


def test_m2_011_to_m3_handoff_has_required_sections() -> None:
    text = _read("m2-to-m3-handoff.md")
    for needle in (
        "# M2 → M3 consolidated handoff",
        "Authority boundary",
        "End-to-end fixture path",
        "m2-code-graph-m3-handoff.md",
        "Empty result",
        "Benchmark arms A–D",
        "No hidden conversation context",
        "Verified commit:",
    ):
        assert needle in text, f"missing section/marker: {needle!r}"
    # Placeholder until stamped, or a 40-char hex commit after follow-up.
    assert (
        "PENDING_M2_011_COMMIT" in text
        or any(
            len(tok) == 40 and all(c in "0123456789abcdef" for c in tok)
            for tok in text.replace("`", " ").split()
        )
    ), "handoff must pin PENDING_M2_011_COMMIT or a stamped commit SHA"
