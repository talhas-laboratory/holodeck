# M2-022 — Implement the Python reference extractor

**Status:** backlog
**Owner:** unassigned
**Depends on:** M2-019, M2-020

## Objective

Implement the first production-compatible extractor adapter using Python's
standard-library AST and deterministic repository metadata.

## Scope

- Extract directories, Python files/modules, classes, functions, methods,
  imports, calls that can be resolved safely, inheritance, tests, manifests,
  configuration, migrations, and basic API entry-point patterns.
- Produce normalized provider candidates through the M2-020 port.
- Verify the checkout's actual commit before and after extraction.
- Enforce include/exclude paths, file-size, file-count, entity, relation, and
  wall-time limits.
- Report unsupported syntax, dynamic dispatch, unresolved imports/calls,
  generated files, binary files, and excluded paths as diagnostics/coverage.
- Pass the reusable provider contract and the M2-019 golden fixture.

## Resolution policy

- Parse only facts directly supported by syntax or deterministic repository
  metadata.
- Resolve import aliases and same-repository definitions where unambiguous.
- Do not create a call edge for reflection, dynamic imports, monkey-patching,
  runtime dependency injection, or ambiguous receiver dispatch.
- Normalize all locators to repository-relative POSIX paths.
- Never execute repository code during extraction.

## Non-goals

- General type inference, deep data/control flow, framework completeness,
  embeddings, generated summaries, or semantic component responsibilities.
- Multi-language support.

## Acceptance criteria

- Repeated extraction of the same revision/configuration produces byte-stable
  normalized candidate output.
- Requested and actual revisions must match.
- Golden entity/relation recall and precision are reported by kind.
- The intentionally dynamic fixture call remains unresolved with a diagnostic.
- Malformed, oversized, unsupported, and changing repositories fail or degrade
  explicitly according to the contract.
- The adapter imports no storage or M3 context-compilation code.

## Verification

```bash
uv run pytest -q tests/test_m2_python_extractor.py
uv run pytest -q tests/test_m2_repository_extractor_contract.py
uv run pytest -q
```

Record fixture precision/recall by relation kind, runtime, changed files, and
known unsupported Python behavior.

## Expected artifacts

- Python extractor adapter.
- Fixture/golden comparison utilities.
- Determinism, limit, revision-race, malformed-file, and diagnostic tests.
