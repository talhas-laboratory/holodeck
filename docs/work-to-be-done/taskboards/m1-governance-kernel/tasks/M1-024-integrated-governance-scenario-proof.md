# M1-024: Prove all integrated governance scenarios

Status: review
Owner: implementation-agent  
Gate: review
Depends on: see TASKS.md  
Reopened: 2026-07-24 release-blocking review (run 7); GS proofs strengthened but milestone not accepted  
Scenarios: GS-001..014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- GS-001..014 have integrated proofs against persisted fixtures under enforced kernel.
- M1-032 structural tenant-coupled ownership (migration v8) is done and required.
- M1-033 structural tenant-coupled authority references (migration v9) is done and required.
- Approval cardinality, tenant-coupled refs, finalized revision immutability,
  evaluation/event envelopes, and application seam have adversarial proofs.
- No M2–M8 capability smuggled into the milestone boundary.

## Observable acceptance

GS-001..014 + `tests/test_governance_release_blockers.py` cover approval
cardinality, cross-tenant ref rejection, DB-level revision immutability, event
envelope fields, and adapter composition seam. GS-008/009 tightened.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_integrated_scenarios.py tests/test_governance_release_blockers.py
python -m pytest -q
```

Result: **252 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Release-blocking + M1-032 ownership + M1-033 authority suite green. Held in
review pending human milestone acceptance with M1-025 after M1-033 dependency.

## Changed files

- `tests/test_governance_integrated_scenarios.py`
- `tests/test_governance_release_blockers.py`
- `src/holodeck_governance/storage/sqlite/migrate_v7.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/composition.py`

## Residual risks

- Bootstrap/admin record creates still use storage repos (documented decision);
  typed create-command envelopes remain deferred.
- Milestone not human-accepted.
