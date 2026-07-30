# M2-026 — Prove factual graph acceptance and publish the M3 handoff

**Status:** done
**Owner:** cursor
**Depends on:** M2-017, M2-023, M2-024, M2-025

## Objective

Prove the complete M2 factual-graph lifecycle on realistic fixtures, document
coverage and operational cost, and publish the exact contracts M3 may rely on.

## Acceptance scenario

1. Onboard a workspace and active repository binding.
2. Build a graph for fixture revision A.
3. Query code entities, dependencies, tests, schemas, and provenance.
4. Move the repository to revision B.
5. Perform incremental refresh and compare it with a full extraction.
6. Prove revision A remains reconstructable.
7. Prove the new graph and source refresh stale only dependent workspace
   intelligence.
8. Exercise timeout, partial coverage, malformed output, replay, crash, and
   concurrent activation.
9. Produce the M3 handoff with query budgets, schemas, limitations, and fixture
   examples.

## Required evidence

- Extraction precision/recall by supported entity/relation kind.
- Full and incremental equivalence on the golden fixture.
- Full/incremental runtime, peak memory if available, fact counts, and reuse
  counts.
- Migration and fresh-install results.
- Tenant isolation, authorization, idempotency, crash recovery, and history.
- Exact event/application outputs.
- Explicit unsupported/dynamic Python cases.
- No provider-generated prompt, interpretation, or instruction entered M2.

## M3 handoff

Publish:

- graph schema and version;
- active/historical snapshot rules;
- bounded query request/result contracts;
- sentinel contracts;
- trust/freshness/provenance semantics;
- error, omission, coverage, and truncation reasons;
- fixture task examples;
- rule that empty results do not clear risk;
- rule that M3 hypotheses remain separate from facts;
- context-quality benchmark arms and predeclared metrics.

Update M2-011 so its final milestone publication includes this handoff.

## Acceptance criteria

- The acceptance scenario passes from a fresh database and checkout.
- All required evidence is stored under the taskboard artifacts.
- The M3 handoff is sufficient for an independent M3 agent.
- M2 readiness accurately reflects partial/unsupported graph coverage.
- Full suite, packaging checks, and relevant CI pass.
- Residual risks are explicit.

## Verification

```bash
uv run pytest -q tests/test_m2_code_graph_acceptance.py
uv run pytest -q
uv build
python -m twine check dist/*
```

Use the repository's actual packaging/CI commands if they differ at execution
time, and record the replacement and reason.

## Expected artifacts

- `artifacts/m2-code-graph-acceptance-evidence.md`.
- `artifacts/m2-code-graph-m3-handoff.md`.
- End-to-end acceptance test.
- Updated M2 board, milestone handoff, and supported-coverage documentation.
