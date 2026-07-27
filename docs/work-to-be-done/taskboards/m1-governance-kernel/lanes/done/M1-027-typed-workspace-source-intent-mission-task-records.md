# M1-027: Add typed workspace, source, intent, mission, and task records

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

Tables in migrations; SqliteRecordRepository write APIs for workspace/source/intent/mission; SqliteTaskRepository for tasks.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_work_and_assignments.py
python -m pytest -q
```

Result: **203 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Tables in migrations; SqliteRecordRepository write APIs for workspace/source/intent/mission; SqliteTaskRepository for tasks.

## Changed files

- `src/holodeck_governance/storage/sqlite/records.py`
- `src/holodeck_governance/storage/sqlite/tasks.py`
- `tests/test_governance_work_and_assignments.py`

## Residual risks

- Work-family creates are repository APIs; governed create commands for workspace/mission remain future.

