# M1-020: Add atomic event-to-outbox creation

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: see TASKS.md  
Reopened: 2026-07-24 review feedback; re-closed after enforced-kernel rework  
Scenarios: see TASKS.md / PACKET_SCENARIO_OWNERS

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Command authorization/state/revision come from durable records where this packet participates in the command path.
- Storage constraints and migrations own material M1 tables for this packet.
- Integrated/unit proofs exercise persisted fixtures rather than caller-supplied evaluator inputs.

## Observable acceptance

Accept path writes event+outbox in same UoW; fault injection before outbox rolls back success set.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py tests/test_governance_lifecycle_uow.py tests/test_governance_outbox.py
python -m pytest -q
```

Result: **203 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Accept path writes event+outbox in same UoW; fault injection before outbox rolls back success set.

## Changed files

- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/storage/sqlite/uow.py`
- `src/holodeck_governance/storage/sqlite/outbox.py`

## Residual risks

- none known for atomic accept path

