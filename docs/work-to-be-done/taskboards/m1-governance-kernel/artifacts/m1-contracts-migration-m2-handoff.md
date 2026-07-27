# M1 contracts, migration guide, and M2 handoff

**Status:** review — artifact ready; milestone not human-accepted (M1-024/025 held).
M1-034 (v10 authority-record issuance), M1-033 (v9 tenant-coupled authority),
and M1-032 (v8 ownership) are done and block 024 acceptance.

## Verified M1 contracts

- Package: `holodeck_governance` (domain / application / storage)
- Application seam: `holodeck_governance.composition.open_governance_app` →
  `GovernanceApplicationService` (adapters must not import SQLite command impl)
- Commands are the sole production lifecycle mutation path:
  - `task.transition`, `run.transition`
  - domain evaluators + `storage.sqlite.command_service` behind the gateway
- Bootstrap/admin record creates may use storage repos until typed create
  envelopes exist (DECISIONS.md run 7).
- Public adapter rejects nested caller-supplied authority/state fields.
- Approval thresholds require distinct authorized approvers (`approve`).
- Tenant-coupled references enforced by migration v7 relationship triggers,
  migration **v8** own-identity / omitted-ref / head-consistency triggers
  (M1-032), and migration **v9** authority reference triggers (revocation↔grant,
  assignment↔actor, grant↔delegator/recipient) plus tenant-scoped revocation
  lookup (M1-033).
- Finalized revisions + append-only ledger tables are DB-immutable (v7).
- Evaluation rows persist primitive results, policy binding, implementation id,
  and selected authority; events carry the catalog envelope fields.
- Authority records carry a persisted issuance basis; rows lacking that basis
  fail closed at runtime.
- Schema: governance migrations **v1–v10**
- Baseline: commit `0adbc1c344ce7f743a6f5ece37501fb096e432d8`
- Verification (2026-07-27): `python -m pytest -q` → **253 collected; no
  failures reported**

## Migration guide (additive)

1. Keep M0 `holodeck_control_plane` tables and HTTP/CLI/MCP adapters for coordination.
2. Apply `migrate_governance(conn)` for `gov_*` tables (through v9).
3. Import legacy rows with `legacy_import` provenance via
   `domain.legacy_mapping` / `storage.sqlite.legacy_import`.
4. Never treat thin-slice mission/acceptance/evidence rows as M1 Approval,
   Evidence, PolicyBinding, Evaluation, or Decision.
5. New governed lifecycle writes must go through `submit_governance_command` /
   `open_governance_app` — never through `Store` into `gov_*`.
6. HTTP/CLI entrypoints:
   - `POST /api/governance/commands`
   - `GET /api/governance/commands/{command_id}/reconstruction?tenant_id=...`
   - `holodeck governance-command --request-json ...`
   - `holodeck governance-reconstruct --tenant-id ... --command-id ...`
7. Graph / authority / policy tables live in migrations v4–v5; record-family
   alignment in v6; enforcement envelopes/triggers in v7; tenant-coupled
   object ownership (own identity + omitted refs + head consistency) in v8;
   tenant-coupled authority references in v9; governed authority-record
   issuance basis in v10.

## M2 handoff

M2 may add collaboration ingress adapters that translate authenticated external
events into M1 commands via the application seam. Do not put Buzz/Slack/GitHub
types in domain modules. Signed actor mapping, external-event inbox, and
provider adapters are M2 scope.

## Scenario proof ownership

M1-024 owns GS-001..014 integrated proofs plus release-blocker adversarial
coverage and remains in **review** until milestone acceptance. M1-025 remains
in **review** with this artifact.
