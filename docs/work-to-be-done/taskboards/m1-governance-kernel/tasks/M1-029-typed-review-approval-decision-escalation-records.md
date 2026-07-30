# M1-029: Add typed review, approval, decision, and escalation records

Status: done
Owner: implementation-agent  
Gate: done
Depends on: see TASKS.md  
Re-closed: 2026-07-24 after P0/P1 residual fixes (run 6); suite evidence refreshed  
Scenarios: supports GS-003, GS-012, GS-013

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)

## Acceptance criteria

- Review/approval/decision/escalation write repos exist.
- DecisionRecord written on accepted commands and reconstructable.
- Approvals used by policy-gated command path; escalations on outbox dead-letter.

## Observable acceptance

DecisionRecord on accept + GS-012/013/003 coverage.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_integrated_scenarios.py -k 'gs003 or gs012 or gs013'
python -m pytest -q tests/test_governance_p1_enforcement.py -k decision
python -m pytest -q
```

Result: **214 passed** (`python -m pytest -q`, 2026-07-24).

Evidence: DecisionRecord persisted and returned by reconstruction; approvals/escalations exercised.

## Changed files

- `src/holodeck_governance/storage/sqlite/records.py`
- `src/holodeck_governance/storage/sqlite/command_service.py`
- `src/holodeck_governance/storage/sqlite/outbox.py`

## Residual risks

- Escalation outbox_item_id linkage optional at some write sites.
