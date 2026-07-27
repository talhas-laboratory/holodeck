# M1-009: Add typed traceability edges

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

SqliteEdgeRepository validates endpoints; graph_seed.persist_edge delegates; dangling/incompatible/cross-tenant tests.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_grants_edges_records.py
python -m pytest -q
```

Result: **203 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: SqliteEdgeRepository validates endpoints; graph_seed.persist_edge delegates; dangling/incompatible/cross-tenant tests.

## Changed files

- `src/holodeck_governance/storage/sqlite/edges.py`
- `src/holodeck_governance/storage/sqlite/graph_seed.py`
- `tests/test_governance_grants_edges_records.py`

## Residual risks

- Edge inserts still require callers to use repository path; raw SQL bypass remains possible outside adapters.

