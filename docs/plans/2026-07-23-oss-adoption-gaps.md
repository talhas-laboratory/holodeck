# OSS adoption gaps

## Goal

Ship Holodeck as an open-source local control plane that anyone can install on their machine and connect to their own tools and agents.

## Verdict

The architecture (local-first SQLite authority, thin HTTP/CLI adapters, project-local policy, zero runtime deps) matches the goal. The gaps below are packaging, identity, and integration maturity — not a need to replace Python or SQLite.

## Prerequisites

Local coordination hardening (TASK-001 through TASK-006) is complete. Remaining OSS work focuses on API documentation (TASK-009), agent adapters (TASK-010), and optional daemon polish (TASK-012).

## Gap register

| ID | Gap | Why it blocks adoption | Follow-on task |
|---|---|---|---|
| G1 | Install is `pip install -e .` from a clone | Resolved: package builds as sdist/wheel and is verified from a clean wheel install; release upload remains owner-approved | TASK-008 (done) |
| G2 | Legacy repository URL and dual-push configuration | Resolved: canonical repository is `holodeck`; the legacy URL redirects there and local pushes target only the canonical remote | TASK-007 (done) |
| G3 | Agent connection is “call raw HTTP yourself” | Tools will not integrate without a stable contract and adapter | TASK-009, TASK-010 |
| G4 | No MCP / SDK / agent protocol surface | Primary 2026 connection path for IDEs and agents; depends on TASK-009 | TASK-010 |
| G5 | Policy is advisory, not enforced | Resolved for disclosure: API, CLI, dashboard, and docs explicitly say it does not enforce or block actions | TASK-011 (done) |
| G6 | stdlib HTTP server is the local daemon | Fine for alpha; polish/expectations gap for a shipped tool | TASK-012 |
| G7 | Multi-agent claim coordination correctness | Resolved: serialized claim acquisition, lifecycle contracts, migration safeguards, and release verification landed in TASK-001 … TASK-006 | TASK-001 … TASK-006 (done) |

## Delivery order

Completed: TASK-001 … TASK-008 and TASK-011 (hardening, canonical identity, installable package, advisory-policy disclosure).

Next:

1. Version and document a small stable HTTP API contract (TASK-009).
2. Ship a first-class MCP (or equivalent) agent adapter over that API (TASK-010; blocked on TASK-009).
3. Evaluate local daemon HTTP polish only if install/API friction remains (TASK-012).

## Explicitly deferred

- Language rewrite (Rust/TypeScript)
- Postgres/MySQL
- Hosted multi-tenant control plane
- Authentication and remote multi-agent networking
- Full policy enforcement adapters and filesystem isolation
- Homebrew / single-binary distribution (optional after PyPI + MCP)

## Acceptance for this track

- One canonical public repo and install story.
- `pip install …` (or equivalent) starts a healthy local runtime without editable checkout.
- Published API contract covers workspaces, tasks, runs, and claims.
- At least one agent adapter (MCP preferred) can claim paths and complete runs against a local instance.
- Docs state clearly that onboarding policy is advisory until enforcement adapters exist.
