# M1-001: Define kernel vocabulary and module contracts

Status: done  
Owner: implementation-agent  
Gate: done  
Scenarios: see TASKS.md / PACKET_SCENARIO_OWNERS

Test specification: [M1 governance test specification](../../../../plans/2026-07-24-m1-governance-test-specification.md)
Depends on: M1-026

## Scope

Define canonical names, ownership, module boundaries, and public contracts for
M1 records. Keep domain, application, storage, and adapter dependencies one-way.

## Current runtime inventory

Read these before changing the contract. Source and tests describe current
behavior; the M1 design describes the target state.

- [`AGENTS.md`](../../../../../AGENTS.md) and the [M1 design](../../../../plans/2026-07-24-m1-durable-governance-kernel-design.md): product constraints and approved target.
- [`store.py`](../../../../../src/holodeck_control_plane/store.py): current SQLite persistence and write paths.
- [`migrations.py`](../../../../../src/holodeck_control_plane/migrations.py): numbered migration framework and current schema upgrade rules.
- [`lifecycle.py`](../../../../../src/holodeck_control_plane/lifecycle.py): current task/run transition logic.
- [`service.py`](../../../../../src/holodeck_control_plane/service.py), [`http_server.py`](../../../../../src/holodeck_control_plane/http_server.py), and [`mcp_server.py`](../../../../../src/holodeck_control_plane/mcp_server.py): existing adapter surfaces that must stay thin.
- [`test_hardening.py`](../../../../../tests/test_hardening.py), [`test_store.py`](../../../../../tests/test_store.py), and [`test_governed_mission.py`](../../../../../tests/test_governed_mission.py): current persistence, migration, lifecycle, and thin-slice coverage.
- [Earlier governed-mission thin-slice design](../../../../plans/2026-07-23-governed-mission-thin-slice-design.md): related in-progress design; preserve it as a migration input rather than assuming it completes M1.

## Acceptance criteria

- Every M1 record has one owning module and contract.
- Domain modules import no adapter, HTTP, database, agent, or provider types.
- The earlier local runtime has an explicit migration seam.
- Record-family, repository/unit-of-work, and error/event catalog packets have
  complete dependency ownership before implementation begins.

## Observable acceptance

- The canonical vocabulary maps every M1 record family to one module, one
  persistence contract, and one implementing packet.
- A dependency/import test proves domain, application, storage, and adapters
  remain one-way.
- The legacy runtime and governed-mission thin slice each have an explicit,
  additive migration seam rather than an implied rewrite.

## Contract

- Package: `holodeck_governance` with layers `domain`, `application`, `storage`.
- Adapters remain in `holodeck_control_plane`.
- Machine-readable ownership: `holodeck_governance.domain.vocabulary`.
- Human mirror: `artifacts/m1-module-contracts.md`.
- Legacy seam: `holodeck_governance.storage.legacy_seam`.

## Verification

Commands:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_governance_module_contracts.py
python -m pytest -q
```

Results:

- Module contract tests: **12 passed**
- Full suite: recorded in UPDATES.jsonl after run completes

## Changed files

- `src/holodeck_governance/__init__.py`
- `src/holodeck_governance/domain/__init__.py`
- `src/holodeck_governance/domain/vocabulary.py`
- `src/holodeck_governance/application/__init__.py`
- `src/holodeck_governance/storage/__init__.py`
- `src/holodeck_governance/storage/legacy_seam.py`
- `tests/test_governance_module_contracts.py`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/artifacts/m1-module-contracts.md`
- `docs/work-to-be-done/taskboards/m1-governance-kernel/DECISIONS.md`
- board index / updates / this packet

## Residual risks

- Repository protocol modules are named but not yet implemented (M1-030).
- Catalog modules are named but not yet published (M1-031).
- none known beyond deferred packet owners

## Non-goals

- Schema implementation or public API expansion.
