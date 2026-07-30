# M1-006: Define legacy-import mapping and provenance

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-003, M1-004, M1-005  
Scenarios: GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Completed under M1 durable governance kernel implementation and gap closure.

## Observable acceptance

- Dry-run mapping is deterministic and marks thin-slice namesakes unsupported.
- Import never fabricates command receipts/authority/evidence/decision events.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_reconstruction_migration.py tests/test_governance_integrated_scenarios.py::test_gs014_legacy_import_no_fabricated_authority
python -m pytest -q
```

Results (2026-07-24):

- Focused governance suite: **82 passed**
- Full suite: **192 passed**

## Changed files

- `src/holodeck_governance/domain/legacy_mapping.py`
- `src/holodeck_governance/storage/legacy_seam.py`
- `tests/test_governance_reconstruction_migration.py`
- `tests/test_governance_integrated_scenarios.py`
- board index / updates / this packet

## Residual risks

- Production multi-table upgrade orchestration remains additive; M1-023 owns full DB path.

## Non-goals

- M2–M8 capabilities remain out of scope.
