# M1-031: Define domain-error, reason-code, and event-schema catalogs

Status: done  
Owner: implementation-agent  
Gate: done  
Depends on: M1-001  
Scenarios: GS-001–GS-014

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)


## Acceptance criteria

- Packet acceptance criteria from the task scope and GATES.md are met.
- Verification commands and results below are the recorded evidence.
- Residual risks are explicit; no M2–M8 scope was smuggled in.

## Scope

Publish versioned, machine-readable catalogs for domain errors, evaluator reason
codes, event types, and event payload schemas. Define ownership, compatibility,
and adapter mappings. The catalog constrains implementation; it is not a
free-form configuration mechanism.

## Observable acceptance

- Every governance scenario names expected catalog identifiers and payload versions.
- Errors distinguish invalid transition, stale revision, missing authority,
  cross-tenant access, malformed command, idempotency conflict, and incomplete
  evaluation without parsing message text.
- Event schemas identify immutable causal metadata and allowed payload fields.

## Contract

- Versions: `m1.errors.v1`, `m1.reasons.v1`, `m1.events.v1`
- Modules: `holodeck_governance.domain.catalogs.{errors,reasons,events,scenario_map}`
- Typed exceptions: `holodeck_governance.domain.errors`
- Adapter map: M0 `ValidationError`/`ConflictError`/`NotFoundError`/`ContentionError`

## Verification

```bash
python -m pytest -q tests/test_governance_catalogs.py tests/test_governance_module_contracts.py
python -m pytest -q
```

Results: catalog+contract **21 passed**; full suite recorded in UPDATES.jsonl.

## Changed files

- `src/holodeck_governance/domain/catalogs/*`
- `src/holodeck_governance/domain/errors.py`
- `tests/test_governance_catalogs.py`
- this packet / TASKS / UPDATES

## Residual risks

- Event payload field lists will grow as command handlers land; additive fields
  require a new payload schema version.
- none known for catalog publication scope

## Non-goals

- Implementing every event ledger table or delivery worker; M1-019 through
  M1-021 implement those consumers.
