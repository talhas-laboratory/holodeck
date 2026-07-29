# M2-011 — Publish M2 contracts and M3 handoff

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-010, M2-017, M2-018, M2-026

## Objective

Publish the stable M2 collaboration, workspace-intelligence, source-context,
and factual-repository-graph contracts plus the explicit handoff required to
start M3, without expanding M2 into mission or execution authority.

## Scope

- Contract index for collaboration intake, task origins/context manifests,
  workspace bindings/genesis, intelligence records, curation/activation,
  source refresh, factual graph snapshots, extractors, bounded queries,
  sentinels, coverage, and provenance.
- Consolidate M2-017 and M2-026 acceptance evidence.
- **M2-026 published** `artifacts/m2-code-graph-m3-handoff.md` (and acceptance
  evidence/metrics); M2-011 must consolidate that graph handoff into the final
  M2→M3 publication. Do not treat M2-026 alone as the milestone close.
- Publish what M2 guarantees, what remains partial/unsupported, and what M3
  must not reinterpret as fact or authority.
- Align board status, decisions, gates, events, API/application seams, schema
  versions, packaging, and migration documentation.

## Non-goals

- Live Buzz adapter (M2-009 remains separately gated).
- Task interpretation, context selection, packets, missions, requirements,
  execution, or acceptance.

## Acceptance criteria

- Every published capability is verified in source/tests at an exact commit.
- Handoff distinguishes implemented behavior from proposal and research.
- M3 receives fixture examples for origin → workspace → factual snapshot →
  bounded query, including partial coverage and empty-result behavior.
- GitNexus is not described as a production dependency without an explicit
  license decision.
- M3 board M3-000 can begin without hidden conversation context.
- Full test/package/CI evidence and residual risks are recorded.

## Verification

```bash
uv run pytest -q
uv build
python -m twine check dist/*
```

Use current repository-equivalent commands if packaging changes and record the
replacement.

## Expected artifacts

- M2 contract index.
- Consolidated M2 acceptance evidence.
- M2-to-M3 handoff linking M2-026 graph handoff
  (`artifacts/m2-code-graph-m3-handoff.md`, already published by M2-026).
- Updated board and milestone documentation.
