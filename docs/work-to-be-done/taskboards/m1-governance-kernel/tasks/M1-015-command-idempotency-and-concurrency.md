# M1-015: Add command idempotency and concurrency control

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-007

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Idempotent retry returns same receipt; semantic conflict raises.
- Competing transitions serialize under BEGIN IMMEDIATE; loser gets STALE_REVISION receipt with evaluation.

## Observable acceptance

Two-connection contention yields one accept + one structured stale reject with evaluation_result_id.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py -k idempot
python -m pytest -q tests/test_governance_p1_enforcement.py -k competing
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Contention + idempotency proofs under enforced kernel (p1 + GS-007).

## Changed files

- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/storage/sqlite/tasks.py`
- `src/holodeck_governance/storage/sqlite/uow.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Contention test covers same expected_revision race; multi-key conflict matrix residual.
