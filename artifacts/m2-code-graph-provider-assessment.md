# M2 code-graph provider assessment

**Date:** 2026-07-29  
**Milestone task:** M2-020  
**Fixture:** `tests/fixtures/code_graph/python_reference`  
**Pinned fixture revisions:**

- `rev_a`: `fixture:c059dce6bb6c4dfa257e2cc1d5d737089fea940091e57090d268dc6dae2c21bb`
- `rev_b`: `fixture:9714592f9bbc4b5c5a7b2548d52d57e88d5af1d43e6e27ac0a9864e0a3ec021e`

## Decision

**Selected M2 implementation provider:** Python standard-library `ast`
(`provider_key=python_stdlib_ast`).

**Not selected for production in M2:**

| Provider | Disposition | Why |
| --- | --- | --- |
| GitNexus | research-only | Current [PolyForm Noncommercial License 1.0.0](https://github.com/nxpatterns/gitnexus/blob/main/LICENSE) does not permit assuming commercial redistribution. No GitNexus code, DB, generated wiki/AGENTS content, or provider schema may enter Holodeck production dependencies without an explicit commercial-license decision. |
| Tree-sitter | deferred multi-language adapter | Preferred later route for broader language coverage behind the same `RepositoryExtractor` port. Not required for the Python-first M2 lane. |
| Joern | research / deep-analysis later | Useful for separately labelled deep static analysis. Out of scope for the initial factual catalog; would remain an optional adapter emitting explicitly limited observation methods. |

Full golden-fixture candidate emission for `python_stdlib_ast` is **M2-022**.
M2-020 proves the replaceable port, conformance kit, offline/stdlib constraints,
and records this selection.

## Gate matrix

| Gate | Python stdlib AST | GitNexus | Tree-sitter | Joern |
| --- | --- | --- | --- | --- |
| 1. License / commercial redistribution | Yes (PSF / stdlib) | No (PolyForm NC) | Yes (MIT) for engines/grammars typically used | Depends on Joern/distribution terms; treat as research until pinned |
| 2. Fixed-revision operation | Yes (checkout path + requested revision) | Research only | Yes, when invoked on a pinned checkout | Research |
| 3. Structured entity/relation export | Yes via Holodeck normalization (M2-022) | Research export only | Yes via adapter normalization | Research |
| 4. Deterministic output at pinned version | Yes (`sys.version` + schema hash) | Not adopted | Yes when grammar/runtime pinned | Research |
| 5. Python fixture accuracy | Conformance kit + fake golden; AST emission in M2-022 | Not run in-process (license) | Not selected for M2 | Not selected for M2 |
| 6. Partial/unsupported coverage reporting | Yes (`CoverageStatus` + diagnostics) | N/A (not imported) | Port supports | Port supports |
| 7. Offline / privacy | Yes | Would require local index; still research-only | Yes | Usually local; research |
| 8. Install / runtime footprint | Zero extra deps | Extra runtime + license risk | Extra native/grammar deps | Heavy |
| 9. Full and incremental behavior | Planned through port (`changed_paths`) | Research | Later adapter | Research |
| 10. Timeout / malformed / stale handling | Request limits + diagnostics | Research | Later adapter | Research |

## Commands and pins executed in this environment

```bash
python3 -c 'import ast, sys; print(sys.version); print(ast.__name__)'
# 3.12.3 ... ; ast

python3 -c 'import importlib.util as u; print(u.find_spec("tree_sitter")); print(u.find_spec("gitnexus"))'
# None ; None

uv run --extra dev pytest -q tests/test_m2_repository_extractor_contract.py
```

No GitNexus package, database, or generated editor/MCP content was installed or
written. Tree-sitter was not added as a dependency.

## Conformance evidence

- Fake adapter serves typed golden facts for `rev_a` and passes
  `run_extractor_conformance`.
- `PythonStdlibAstExtractor` describes offline Python capabilities, parses the
  fixture tree with stdlib `ast`, and returns honest **partial** coverage with
  an `extractor_deferred` diagnostic until M2-022 emits candidates.

## Residual risks

- AST extractor completeness is deferred to M2-022; do not treat M2-020 partial
  results as an active graph snapshot.
- GitNexus remains attractive as a quality reference; keep assessments against
  primary license text before any future adapter work.
