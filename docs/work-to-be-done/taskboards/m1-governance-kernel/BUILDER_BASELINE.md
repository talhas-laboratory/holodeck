# Fresh-builder baseline

This is the M1 handoff contract for an agent beginning from a fresh checkout.
It distinguishes the accepted runtime baseline from unfinished local work.

## Accepted baseline snapshot

| Field | Value |
| --- | --- |
| Branch | `codex/publish-current-m1-state` |
| Commit | `0adbc1c344ce7f743a6f5ece37501fb096e432d8` |
| Message | `docs: add governance planning and mission foundation` |
| Worktree at claim | clean (`git status --short` empty) |
| Recorded by | M1-026 on 2026-07-24 |
| Verification | `python -m pip install -e ".[dev]" && python -m pytest -q` → **110 passed** (Python 3.13.7) |

This commit is the accepted M0 compatibility baseline for all subsequent M1
schema and runtime work. Unrelated dirty-tree material that existed when the
board was planned is already incorporated into this commit or discarded; do not
treat planning docs as proof that an M1 capability is complete.

## Supported bootstrap

From a clean checkout with Python 3.11 or later:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

The editable install plus `python -m pytest` is the supported handoff command.
`PYTHONPATH=src` is diagnostic-only.

## Current runtime inventory (M0)

Package: `holodeck-control-plane` / `src/holodeck_control_plane/`

| Module | Role |
| --- | --- |
| `store.py` | SQLite persistence and coordination write paths |
| `migrations.py` | Numbered migrations 1–3 (`relational_integrity`, `workspace_fk_and_claim_safeguards`, `governed_missions`) |
| `lifecycle.py` | Task/run status sets and transition validation |
| `service.py` | Application facade over the store |
| `api.py`, `http_server.py`, `http_client.py`, `http_request.py` | HTTP adapter surface |
| `cli.py` | CLI adapter |
| `mcp_server.py` | Optional MCP adapter |
| `ids.py` | Legacy string identifier validation (not UUIDv7) |
| `errors.py` | `HolodeckError`, `ValidationError`, `ConflictError`, `NotFoundError`, `ContentionError` |
| `paths.py`, `validation.py`, `project.py` | Path canonicalization, request validation, project init |

Current tables: `schema_migrations`, `workspaces`, `tasks`, `runs`, `claims`,
plus governed-mission thin-slice tables `workspace_sources`,
`curator_proposals`, `missions`, `mission_evidence`, `acceptance_decisions`.

Tests under `tests/` cover store, hardening, HTTP, MCP, API contract, policy
boundary, project identity, release, and the governed-mission thin slice.

## Compatibility decisions (implementation owners)

These are fixed before M1 persistence code lands. Implementation packets own
the tests; this baseline only records the chosen approach.

### Python 3.11 UUIDv7 compatibility — owner M1-004

Supply a small, tested internal UUIDv7-compatible generator in the governance
domain. Do not call a newer standard-library UUIDv7 API as the sole path, and
do not add an ID-only runtime dependency. IDs remain opaque; time-ordering is
an implementation property, never an authorization input.

### Legacy lifecycle import dispositions — owner M1-006 / proof M1-023

Every current status is imported as a `legacy_import` fact. Values are **not**
silently relabeled as M1-governed transitions. Planned one-way dispositions:

| Legacy surface | Value | M1 disposition |
| --- | --- | --- |
| Task | `backlog` | map → M1 task state `draft` (import fact only) |
| Task | `ready` | map → M1 task state `ready` |
| Task | `in-progress` | map → M1 task state `active` |
| Task | `review` | map → M1 task state `submitted` |
| Task | `blocked` | map → M1 task state `blocked` |
| Task | `done` | map → M1 task state `accepted` |
| Task | `cancelled` | map → M1 task state `cancelled` |
| Run | `active` | map → M1 run state `active` |
| Run | `completed` | map → M1 run state `completed` |
| Run | `failed` | map → M1 run state `failed` |
| Run | `cancelled` | map → M1 run state `cancelled` |
| Claim | `active` / `released` | preserve as coordination facts; no M1 authority semantics |
| Mission thin-slice | `missions.status`, `acceptance_decisions`, `mission_evidence`, `curator_proposals` | import with `legacy_import` provenance only; **unsupported** as M1 Approval, Evidence, PolicyBinding, Evaluation, or Decision until re-created via commands |

M1 lifecycle targets (from design):  
`Task: draft → ready → active → submitted → accepted | blocked | cancelled`  
`Run: created → active → completed | failed | interrupted | cancelled`  
Legacy has no `created` or `interrupted` run states; those remain M1-native only.

### SQLite typed-edge enforcement — owner M1-009 / GS-005

1. Every endpoint first has a typed `governance_object` registry row.
2. Edge rows reference registry IDs and an allowed-edge-type matrix.
3. Foreign keys enforce endpoint existence and same-tenant ownership.
4. A SQLite trigger **or** same-boundary domain validation (both covered by
   GS-005) enforces the endpoint-type matrix.
5. Core relations never live only in JSON.

### Transactional ownership — owner M1-030

Repositories expose typed persistence contracts. Application commands open one
unit of work. Only that unit of work may commit receipt, evaluation,
transition, event, outbox, and record-head changes.

## Preservation rule

- Existing HTTP/CLI/MCP behavior remains through thin adapters until M1-023
  parity evidence exists.
- M1 migrations are additive.
- Never describe legacy or thin-slice records as M1-governed approvals,
  evidence, policies, evaluations, or decisions unless created through the M1
  command path.

## Required first reads

- `AGENTS.md`
- `docs/product-vision/README.md`
- `docs/product-vision/PRODUCT_VISION.md`
- `docs/product-vision/DECISION_GUIDE.md`
- M1 design, test specification, taskboard, decisions, and updates
