# M2-020 — Establish extractor port and provider assessment

**Status:** done
**Owner:** cursor
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
uv run --extra dev pytest -q tests/test_m2_repository_extractor_contract.py
uv run --extra dev pytest -q
```

Results: contract tests passed; full suite `438 passed in 40.75s`.

## Evidence and handoff

- Port: `holodeck_governance.application.repository_extractor`
- Conformance: `repository_extractor_conformance.run_extractor_conformance`
- Fake adapter + `PythonStdlibAstExtractor` (honest partial until M2-022)
- Assessment: `artifacts/m2-code-graph-provider-assessment.md`
- Selected provider: `python_stdlib_ast`; GitNexus research-only; Tree-sitter deferred

## Residual risks

- Full AST candidate emission remains M2-022.
- Do not activate partial M2-020 AST results as a graph snapshot.
