# Handoffs

## 2026-07-24 — M1-033 tenant-coupled authority (run 9)

**Verdict:** M1-033 complete. Migration **v9** enforces tenant-coupled authority
references (revocations, role assignments, delegated grants). Milestone still
**not** accepted.

### Board

- **Done:** M1-033 (blocks M1-024), M1-032
- **Review:** M1-024, M1-025

### Evidence

- `tests/test_governance_tenant_coupled_authority.py`
- Fresh migrate → version 9; v8→v9 upgrade preserves valid rows
- Beta cannot insert/update revocation for Alpha grant
- Planted Beta revocation ignored by tenant-scoped lookup
- Same-tenant revocation still denies; same-tenant assignment/grant succeed

### Verification

Result: **252 passed** (`python -m pytest -q`).

---

## 2026-07-24 — M1-032 tenant-coupled ownership (run 8)

**Verdict:** M1-032 complete. Migration **v8** enforces tenant-coupled object
ownership for row identity and omitted relationship refs. Milestone still
**not** accepted.

### Board

- **Done:** M1-032 (blocks M1-024)
- **Review:** M1-024, M1-025

### Evidence

- `tests/test_governance_tenant_coupled_ownership.py`
- Fresh migrate → version 8; v7→v8 upgrade preserves valid rows
- Adversarial raw-SQL proofs for Alpha/Beta identity and relationship mismatches

### Verification

Result: **243 passed** (`python -m pytest -q`).

---

## 2026-07-24 — Release-blocking fixes (run 7)

**Verdict:** Six release-blocking gaps from review are fixed in code with
adversarial tests. Milestone remains **not** accepted.

### Fixes

1. **Approval cardinality** — distinct authorized (`approve`) approvers for the
   exact subject revision; `required_approvals=2` + one approval rejects.
2. **Tenant-coupled refs** — migration v7 INSERT/UPDATE triggers abort
   cross-tenant typed references.
3. **Finalized revision immutability** — UPDATE/DELETE triggers on finalized
   revisions; append-only triggers on ledger/eval/receipt/transition tables.
4. **Evaluation evidence** — persist primitive_results, policy_binding_id,
   evaluator_implementation_id, selected_authority; GS-008 asserts them.
5. **Event envelope** — persist actor_id, payload_schema_version, occurred_at,
   subject refs on `gov_domain_events`.
6. **Application seam** — adapters use `open_governance_app` /
   `GovernanceApplicationService`; no direct SQLite CommandService import.

### Board

- **Review:** M1-024, M1-025
- Milestone **not** accepted; do not commit acceptance without human sign-off.

### Verification

Result: **222 passed** (`python -m pytest -q`).

---

## 2026-07-24 — GATES re-close after P0/P1 (run 6 closeout)

**Verdict:** Implementation packets re-closed under GATES with suite evidence.
Milestone remains **not** accepted.

### Board

- **Done (re-closed):** M1-010, 012–015, 022–024, 028–030
- **Review (held):** M1-025 — contracts/M2 handoff artifact exists; awaiting
  human milestone acceptance
- **In progress:** none

### Evidence

- `python -m pytest -q` → **214 passed**
- Packet acceptance criteria refreshed against enforced-kernel + P0/P1 fixes
  (grant reasons, jurisdiction, reconstruction DecisionRecord, edge migrate
  fail-closed, contention eval, run perm, outbox fencing, nested adapter forbid)

### Do not

- Do **not** mark the milestone complete until M1-025 is human-accepted.

---

## 2026-07-24 — P0 residual fixes (run 6)

**Verdict:** Deep-review P0s and key P1s are fixed. Milestone still **not**
accepted; packets remain open pending GATES re-close.

### P0 fixes

1. **Grant deny reasons** — removed `for`/`else` overwrite that clobbered
   expired/revoked/wrong-revision with `DENY_MISSING_AUTHORITY`.
2. **Jurisdiction fail-closed** — workspace jurisdiction enforced; unknown
   subject workspace no longer authorizes.
3. **Reconstruction DecisionRecord** — `ReconstructedDecision.decisions`
   populated from `gov_decisions` / command subject links; adapter + GS-013.
4. **Edge migrate fail-closed** — failed edge copy raises and preserves the
   live `gov_traceability_edges` table (no DROP-after-failed-copy).

### P1 fixes

5. Contention reject now persists evaluation snapshot/result.
6. `run.transition` no longer falls back to `transition_task`.
7. `RoleProfile.jurisdiction` persisted as `jurisdiction_json` (v5 + v6 ADD).
8. Outbox `record_attempt` requires `lease_owner` fencing.
9. Adapter rejects nested forbidden authority fields.
10. migrate_v6 refuses to wipe non-empty evidence that cannot be remapped.

### Verification

Result: **214 passed** (`python -m pytest -q`).

Do **not** mark milestone done until packet GATES re-close.

---

## 2026-07-24 — P1 reopen after milestone challenge (run 5)

**Verdict:** M1 is **not** complete. Four P1 blockers from review are fixed in
code and covered by new tests; affected packets reopened to `in-progress`.

### Fixes landed

1. **Competing transitions** — `apply_transition` re-reads head under UoW
   `BEGIN IMMEDIATE`; IntegrityError → `StaleRevisionError`; accept path writes
   a structured stale rejection receipt for the loser.
2. **Authority immutability** — `INSERT` only (no `OR REPLACE`); duplicate keys
   raise `RevisionImmutableError`.
3. **migrate_v5 data preserve** — stash `*_pre_v5`, recreate, copy common
   columns (synthesize `command_id` for legacy transitions), then drop stash.
4. **Run + Decision** — `run.transition` command path + `DecisionRecord` on
   accepted task/run transitions (linked for reconstruction).

### Tests added

- `tests/test_governance_p1_enforcement.py`
  - two-connection competing transition
  - authority overwrite rejection
  - pre-v5 command/outbox upgrade fixture
  - run transition + decision e2e

### Board

Reopened: M1-010, 012–015, 022–025, 028–030. Do **not** mark milestone done.

### Verification

Result: **207 passed** (`python -m pytest -q`).

---

## Earlier runs

See `UPDATES.jsonl` for enforced-kernel runs 1–4 and prior closeout history.
