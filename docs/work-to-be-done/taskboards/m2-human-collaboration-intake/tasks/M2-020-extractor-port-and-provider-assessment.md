# M2-020 — Establish extractor port and provider assessment

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-019

## Objective

Create the replaceable repository-extractor boundary and produce a reproducible
provider assessment that decides which tools may be used in production,
research, or later adapters.

## Scope

- Define application-facing `RepositoryExtractor`,
  `ExtractionRequest`, `ExtractionResult`, capability, diagnostic, coverage,
  limit, and provider-descriptor contracts.
- Add a provider conformance test kit based on the M2-019 fixture.
- Assess GitNexus, Python AST, Tree-sitter, and optionally Joern against the
  decision matrix in the design.
- Pin every evaluated tool/version and record exact commands and outputs.
- Record license/redistribution conclusions in `DECISIONS.md`.
- Select the M2-022 implementation provider without changing the domain schema.

## Required decision

GitNexus currently uses the PolyForm Noncommercial License 1.0.0. Treat it as a
research reference only unless an authorized commercial-license decision is
recorded. No GitNexus code, database, generated AGENTS/CLAUDE content, or
provider schema may enter Holodeck production dependencies during this task.

The default implementation decision is Python standard-library AST. Tree-sitter
is the preferred later multi-language adapter. Override only with recorded
license, runtime, determinism, and fixture evidence.

## Provider gates

Evaluate:

1. license and commercial redistribution;
2. fixed-revision operation;
3. structured entity/relation export;
4. deterministic output at a pinned version;
5. Python fixture accuracy;
6. partial/unsupported coverage reporting;
7. offline and privacy behavior;
8. installation/runtime footprint;
9. full and incremental behavior;
10. timeout, malformed output, and stale-index handling.

## Non-goals

- Shipping a production provider.
- Adopting a provider database as Holodeck authority.
- MCP prompt retrieval, embeddings, clustering, generated wikis, or semantic
  interpretation.

## Acceptance criteria

- Domain/application modules import no provider SDK.
- The conformance kit can run against a fake provider and the selected adapter.
- Requests require immutable revisions and explicit resource/path limits.
- Results report actual revision, provider identity/version/schema, coverage,
  candidates, and diagnostics.
- The assessment matrix contains primary-source license links and reproducible
  fixture evidence.
- `DECISIONS.md` records the selected M2 provider and why alternatives are
  research-only, deferred, or rejected.

## Verification

```bash
uv run pytest -q tests/test_m2_repository_extractor_contract.py
uv run pytest -q
```

Any external-provider smoke test must run from a temporary directory, must not
modify global editor/MCP configuration, and must record its exact pinned
version.

## Expected artifacts

- Extractor port and fake adapter.
- Reusable provider contract test.
- `artifacts/m2-code-graph-provider-assessment.md`.
- Durable provider decision in the M2 board.
