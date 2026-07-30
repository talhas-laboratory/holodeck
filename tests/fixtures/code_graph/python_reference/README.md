# Python reference fixture for factual code-graph contracts

Two deterministic trees (`trees/rev_a`, `trees/rev_b`) plus typed golden facts.

## Revisions

Content identities are `fixture:<sha256>` values recorded in `revisions.json`.
They are computed from sorted repository-relative paths and file bytes.

`rev_b` changes:

- `sample_app/service.py` — greeting text and new `Greeter.shout`
- `tests/test_service.py` / `tests/test_api.py` — expectations

## Unresolved dynamic call

`Greeter.invoke` uses `globals()[handler_name]`. Golden diagnostics record
`unresolved_dynamic_call`; no fabricated `CALLS` edge is allowed.

## Golden facts

`golden/rev_a.py` constructs domain `CodeEntityFact` / `CodeRelationFact`
records covering every initial relation kind. Deferred kinds from this fixture
are listed explicitly as an empty frozenset.
