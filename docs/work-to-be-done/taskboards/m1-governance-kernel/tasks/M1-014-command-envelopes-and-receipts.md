# M1-014: Add command envelopes and immutable receipts

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: GS-007, GS-011

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- CommandService resolves auth/state from durable records.
- Receipts immutable; adapter rejects caller-supplied and nested forbidden fields.
- Accepted commands write DecisionRecord + receipt/eval/event/outbox.

## Observable acceptance

Public adapter nested forbid + CommandService sole mutation entry; DecisionRecord on accept.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py tests/test_governance_adapter_boundary.py tests/test_governance_p1_enforcement.py -k nested
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Adapter nested forbid + command path receipts under enforced kernel.

## Changed files

- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_control_plane/governance_commands.py`
- `tests/test_governance_adapter_boundary.py`
- `tests/test_governance_p1_enforcement.py`

## Residual risks

- Domain evaluators still accept resolved facts as parameters; only public adapters/CommandService are enforced.
