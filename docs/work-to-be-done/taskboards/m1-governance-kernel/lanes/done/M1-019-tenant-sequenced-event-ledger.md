# M1-019: Add tenant-sequenced domain event ledger

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

Accepted commands append domain events in UoW; GS-001 isolation rejects write receipt without event.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_commands.py tests/test_governance_integrated_scenarios.py
python -m pytest -q
```

Result: **203 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: Accepted commands append domain events in UoW; GS-001 isolation rejects write receipt without event.

## Changed files

- `src/holodeck_governance/storage/sqlite/repos.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/storage/sqlite/migrate_v5.py`

## Residual risks

- Tenant sequence numbers are insert-order based; explicit sequence column not required for M1 reconstruction.

