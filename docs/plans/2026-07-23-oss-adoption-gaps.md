# OSS adoption gaps

## Goal

Ship Holodeck as an open-source local control plane that anyone can install on their machine and connect to their own tools and agents.

## Verdict

The architecture (local-first SQLite authority, thin HTTP/CLI adapters, project-local policy, zero runtime deps) matches the goal. The gaps below are packaging, identity, and integration maturity — not a need to replace Python or SQLite.

## Prerequisites

Local coordination hardening and the OSS adoption tasks (TASK-001 through TASK-012) are complete.

## Gap register

| ID | Gap | Why it blocks adoption | Follow-on task |
|---|---|---|---|
| G1 | Install is `pip install -e .` from a clone | Resolved: package builds as sdist/wheel and is verified from a clean wheel install; release upload remains owner-approved | TASK-008 (done) |
| G2 | Legacy repository URL and dual-push configuration | Resolved: canonical repository is `holodeck`; the legacy URL redirects there and local pushes target only the canonical remote | TASK-007 (done) |
| G3 | Agent connection is “call raw HTTP yourself” | Resolved: `http-api-v1` contract documented and versioned in `/api/config`; MCP adapter exposes IDE/agent tooling over the same authority | TASK-009 (done), TASK-010 (done) |
| G4 | No MCP / SDK / agent protocol surface | Resolved: `holodeck mcp` stdio adapter with nine tools over the documented HTTP API | TASK-010 (done) |
| G5 | Policy is advisory, not enforced | Resolved for disclosure: API, CLI, dashboard, and docs explicitly say it does not enforce or block actions | TASK-011 (done) |
| G6 | stdlib HTTP server is the local daemon | Resolved for local alpha: measured API/MCP traffic, stalled-client timeout, and shutdown behavior support retaining the hardened stdlib server; its limits are documented | TASK-012 (done) |
| G7 | Multi-agent claim coordination correctness | Resolved: serialized claim acquisition, lifecycle contracts, migration safeguards, and release verification landed in TASK-001 … TASK-006 | TASK-001 … TASK-006 (done) |

## Delivery order

Completed: TASK-001 … TASK-012 (hardening, canonical identity, installable package, HTTP API contract, MCP adapter, advisory-policy disclosure, and local-daemon evaluation).

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
