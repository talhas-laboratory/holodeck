# M3-000 — Validate M3 entry, handoff, and benchmark protocol

**Status:** ready
**Owner:** unassigned
**Depends on:** M2-011 (done — handoff artifacts published)

## Objective

Prove M2 supplies every stable input M3 needs and preregister the experiment
that will decide whether graph retrieval and task-local interpretation improve
agent quality.

## Scope

- Graph handoff path ready from M2-026: `artifacts/m2-code-graph-m3-handoff.md`.
- Final consolidation ready from M2-011:
  - `artifacts/m2-to-m3-handoff.md`
  - `artifacts/m2-contracts-index.md`
  - `artifacts/m2-consolidated-acceptance-evidence.md`
- Validate M2 task-origin, source-manifest, workspace-model, source/module,
  readiness, repository snapshot, query, sentinel, provenance, coverage, error,
  and omission contracts.
- Create representative task corpus categories and expert-labelled expected
  context/impact surfaces.
- Lock benchmark arms A–D, model/harness versions, budgets, permissions,
  repetitions, metrics, and promotion/stop thresholds (preregistered in M2
  handoff §9 / graph handoff §10 — M3-000 must lock numbers).
- Record missing M2 inputs as blockers; do not patch around them in M3.
- Establish baseline full-suite and package evidence.

## Acceptance criteria

- Every M3 input is pinned to a schema/version and fixture example.
- The benchmark protocol prevents changing thresholds after observing results.
- High-risk false negatives are reported separately from averages.
- An independent builder can begin M3-001 without reading prior chat.

## Verification

```bash
uv run pytest -q
uv build
```

## Expected artifacts

- `artifacts/m3-entry-and-m2-contract-matrix.md`.
- `artifacts/m3-context-quality-benchmark-protocol.md`.
- Accepted or blocked board decision.

## Note

Handoff artifacts are ready. This task still requires M3-000 validation work
(matrix + locked benchmark protocol); publication of M2-011 alone is not
completion of M3-000.
