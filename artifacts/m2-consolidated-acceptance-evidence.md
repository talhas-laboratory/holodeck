# M2 consolidated acceptance evidence

**Published by:** M2-011  
**Date:** 2026-07-29  
**Verified commit:** `322317816bb83721b2ec361cb3f66e704cf0e4c3`  
**Governance schema:** **v24+** (fresh `migrate_governance`)

This consolidates M2-017 (workspace onboarding/refresh), M2-010 (E2E intake),
M2-026 (factual graph acceptance), and packaging evidence into one milestone
record. Detailed step tables remain in linked artifacts; do not treat this as a
substitute for reading the graph handoff.

---

## Scenarios that passed

### M2-010 — E2E authenticated intake (memory harness)

Test: `tests/test_m2_e2e_memory_intake.py` → **7 passed** (historical board
record; re-verified in full suite below).

| Scenario family | Result |
| --- | --- |
| CIS-001 auth refusal (`CollaborationAdapterAuthError`; no receipt) | **pass** |
| Unauthorized / rejected intake | **pass** |
| Duplicate delivery → `duplicate_replay`, same origin | **pass** |
| Cross-tenant isolation | **pass** |
| Non-intake ordinary conversation (no origin) | **pass** |
| Happy path: verified intake → origin → correlated outbound (no mission/run) | **pass** |
| Crash/retry / replay recovery through orchestrator | **pass** |

### M2-017 — Workspace onboarding and refresh

Test: `tests/test_m2_017_onboarding_refresh_acceptance.py` → **1 passed**.

| Step | Result |
| --- | --- |
| Onboard workspace intelligence model | **pass** |
| Discover/register sources | **pass** |
| Reject assured-readiness bypass without evidence | **pass** |
| Resolve gap; HUMAN trust + readiness decisions | **pass** |
| Activate GOVERNED curation | **pass** |
| Refresh immutable source observations | **pass** |
| Query intelligence snapshot | **pass** |
| No Mission / Run created | **pass** |

### M2-026 — Factual code-graph acceptance

Test: `tests/test_m2_code_graph_acceptance.py` → **2 passed**.  
Detail: `artifacts/m2-code-graph-acceptance-evidence.md` +
`artifacts/m2-026-acceptance-metrics.json`.

| Step | Result |
| --- | --- |
| Fresh migrate ≥ v24 + curate + active repository binding | **pass** |
| Build `rev_a` via `CodeGraphIngestionService` + `PythonStdlibAstExtractor` | **pass** |
| Bounded queries + sentinels + provenance | **pass** |
| Incremental refresh to `rev_b` ≡ full rebuild (normalized) | **pass** |
| Historical `rev_a` after supersede | **pass** |
| Changed-source stale propagation (selective modules) | **pass** |
| Partial coverage does not activate; revision mismatch fails closed | **pass** |
| Idempotent replay; concurrent single-active activation | **pass** |
| Events free of prompt/interpretation authority strings | **pass** |

### M2-018 — Conversation context (supporting, not separate E2E gate here)

Tests: `tests/test_m2_conversation_context.py`,
`tests/test_m2_018_messy_slack_thread_fixture.py` — covered in full suite.

---

## Schema version

- Governance SQLite after empty `migrate_governance`: **24**
- Code-graph logical schemas: `m2.code_graph.v1` family (see contracts index)
- Workspace intelligence / collaboration record schemas: see
  `artifacts/m2-contracts-index.md`

---

## Test counts / package check commands

Recorded for this M2-011 publication run:

```bash
uv run --extra dev pytest -q
# -> 490 passed in 49.62s

uv build
# -> Successfully built dist/holodeck_control_plane-0.1.0.tar.gz
#    Successfully built dist/holodeck_control_plane-0.1.0-py3-none-any.whl

uvx twine check dist/*
# -> Checking dist/holodeck_control_plane-0.1.0-py3-none-any.whl: PASSED
#    Checking dist/holodeck_control_plane-0.1.0.tar.gz: PASSED
# (uvx used because python -m twine was not preinstalled in the env)
```

Focused counts:

| Packet | Command | Result |
| --- | --- | --- |
| M2-011 smoke | `pytest -q tests/test_m2_011_handoff_artifacts.py` | 3 passed |
| M2-010 | `pytest -q tests/test_m2_e2e_memory_intake.py` | 7 passed (in suite) |
| M2-017 | `pytest -q tests/test_m2_017_onboarding_refresh_acceptance.py` | 1 passed (in suite) |
| M2-026 | `pytest -q tests/test_m2_code_graph_acceptance.py` | 2 passed (in suite) |

---

## Residual risks

1. **Buzz (M2-009)** remains gated — no live collaboration ingress.
2. Structural graph precision vs golden is low for `contains` / `defines` /
   `imports` (high recall on supported behavioral kinds).
3. Impact-neighborhood re-extraction may stamp new observations on unchanged
   bytes; rename/delete without trusted `changed_paths` needs full fallback.
4. Empty query results and unresolved sentinels never prove absence of risk.
5. Partial coverage cannot activate without a durable policy-decision seam.
6. **GitNexus** research-only (PolyForm NC) — not a production dependency.
7. Typed collaboration/intelligence command handlers may still use the
   bootstrap/admin persistence exception in places.
8. M3 must lock benchmark arms A–D thresholds in M3-000 before observing
   agent-quality results (preregistration only in graph handoff §10).
9. Python AST worktree-backed extraction requires clean worktree / exact
   revision match for Git-backed paths.

---

## Links to detailed artifacts

| Artifact | Role |
| --- | --- |
| `artifacts/m2-contracts-index.md` | Capability → schema → seam → tests |
| `artifacts/m2-to-m3-handoff.md` | Independent M3 start packet |
| `artifacts/m2-code-graph-m3-handoff.md` | Graph schema, APIs, fixtures, rules |
| `artifacts/m2-code-graph-acceptance-evidence.md` | M2-026 step evidence |
| `artifacts/m2-026-acceptance-metrics.json` | M2-026 metrics |
| `artifacts/m2-022-python-extractor-metrics.json` | Extractor P/R |
| `artifacts/m2-024-incremental-refresh-metrics.json` | Full≡incremental |
| `artifacts/m2-025-code-graph-queries-metrics.json` | Query/sentinel metrics |
| `artifacts/m2-code-graph-provider-assessment.md` | Provider / GitNexus license |
| `tests/test_m2_017_onboarding_refresh_acceptance.py` | Onboarding acceptance |
| `tests/test_m2_e2e_memory_intake.py` | Intake E2E |
| `tests/test_m2_code_graph_acceptance.py` | Graph acceptance |
