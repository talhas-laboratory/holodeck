# M1-011: Add role assignments and jurisdiction checks

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

CommandService resolves actor_may_transition from persisted assignments; missing-authority path rejects without caller permission input.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py tests/test_governance_work_and_assignments.py
python -m pytest -q
```

Result: **203 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: CommandService resolves actor_may_transition from persisted assignments; missing-authority path rejects without caller permission input.

## Changed files

- `src/holodeck_governance/storage/sqlite/authority.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/testing/seed.py`

## Residual risks

- Jurisdiction is workspace-scoped for transition_task; finer object-level jurisdiction deferred.

