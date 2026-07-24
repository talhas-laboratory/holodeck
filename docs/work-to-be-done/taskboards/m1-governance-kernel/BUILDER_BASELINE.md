# Fresh-builder baseline

This is the M1 handoff contract for an agent beginning from a fresh checkout.
It distinguishes the accepted runtime baseline from unfinished local work.

## Supported bootstrap

From a clean checkout with Python 3.11 or later:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

The editable install plus `python -m pytest` is the supported handoff command.
`PYTHONPATH=src` is diagnostic-only.

## Baseline and preservation rule

The existing SQLite coordination runtime is the M0 compatibility baseline. Its
source and tests, not planning documents, describe current behavior.

When this board was prepared, the worktree contained uncommitted governed-
mission, planning, product-vision, and taskboard-relocation work. These are
**migration inputs**, not proof that an M1 capability is complete. A claiming
agent must inspect `git status --short`, preserve unrelated changes, record the
exact commit or user-approved snapshot used, and never describe legacy records
as M1 approvals, evidence, policies, evaluations, or decisions unless they are
created through the M1 command path.

Without a clean commit or user-approved snapshot, work is limited to additive
documentation, contracts, and tests. Schema or runtime changes must first
record the selected baseline in `HANDOFFS.md`.

## Compatibility decisions to preserve

- Python starts at 3.11. M1 supplies a tested internal UUIDv7-compatible
  generator; no ID-only runtime dependency is added.
- Current task/run statuses are `legacy_import` facts until M1-006 publishes a
  one-way mapping or an explicit unsupported disposition.
- M1 migrations are additive. Existing HTTP/CLI behavior remains through thin
  adapters until M1-023 parity evidence exists.
- SQLite typed edges use an object registry and edge compatibility matrix;
  endpoint existence, tenant match, and type compatibility are enforced and
  tested, never advisory JSON.

## Required first reads

- `AGENTS.md`
- `docs/product-vision/README.md`
- `docs/product-vision/PRODUCT_VISION.md`
- `docs/product-vision/DECISION_GUIDE.md`
- M1 design, test specification, taskboard, decisions, and updates

