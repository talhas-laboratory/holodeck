# M3-009 — Run comparative quality benchmark and publish M4 handoff

**Status:** backlog
**Owner:** unassigned
**Depends on:** M3-008

## Objective

Measure whether typed intake, factual graph retrieval, and task-local
interpretation improve real coding quality, then enable only the stages that
beat their cheaper baseline.

## Benchmark arms

```text
A. ordinary agent search
B. A + typed task intake and cheap sentinels
C. B + bounded factual-graph retrieval
D. C + task-local interpretive probes
```

Hold model, harness, tools, permissions, repository revision, task prompt,
token/time budget, retry count, and evaluation tests constant.

## Task strata

- local edits;
- cross-module behavior;
- schema/API changes;
- authorization/security changes;
- caching, retry, timing, or concurrency changes.

## Metrics

Primary:

- accepted patch rate;
- consequential affected-component recall;
- regression and high-risk false-negative rate;
- required-test and invariant coverage.

Secondary:

- context precision/recall/F1 and utilized context;
- tokens, latency, tool calls, extraction/refresh cost;
- stale-context failures and human-review burden.

## Decision rules

- Compare C with B to decide whether graph retrieval is product-enabled.
- Compare D with C to decide whether each probe is product-enabled.
- Report high-risk false negatives separately.
- Do not average away task-class regressions.
- Do not change preregistered thresholds after observing results.
- Disable or retain as experimental any stage that does not pass.

## M4 handoff

Publish accepted mission, context, assumption, ambiguity, authority, required
output, evidence-expectation, and unresolved-risk contracts. M4 will compile
requirements, test strategies, oracles, and gates; M3 must not pre-implement
them.

## Acceptance criteria

- Every benchmark arm completes under the preregistered equal conditions or
  records a comparable explicit failure.
- Raw results, environment/model/harness versions, repetitions, and analysis
  remain reproducible.
- C receives a product decision relative to B; each D probe receives a separate
  decision relative to C.
- No aggregate metric hides a regression or false negative in a high-risk task
  class.
- Non-improving capabilities are disabled or clearly labelled experimental.
- The M4 handoff is sufficient for an independent M4 builder and contains no
  hidden mission-compilation assumptions.

## Verification

```bash
uv run pytest -q tests/test_m3_end_to_end.py
uv run pytest -q
uv build
python -m twine check dist/*
```

Also run the exact preregistered benchmark command and preserve raw results,
environment metadata, summaries, and promotion decisions.

## Expected artifacts

- `artifacts/m3-context-quality-benchmark-results.md`.
- Machine-readable raw benchmark results.
- Enabled/experimental/disabled capability decision.
- `artifacts/m3-contracts-m4-handoff.md`.
