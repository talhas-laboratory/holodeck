# OSS adoption gaps

## Goal

Ship Holodeck as an open-source local control plane that anyone can install on their machine and connect to their own tools and agents.

## Verdict

The architecture (local-first SQLite authority, thin HTTP/CLI adapters, project-local policy, zero runtime deps) matches the goal. The gaps below are packaging, identity, and integration maturity — not a need to replace Python or SQLite.

## Prerequisites

Tasks TASK-001 through TASK-006 (local coordination hardening) remain first. OSS packaging and adapters should not ship on an incorrect claim/lifecycle core.

## Gap register

| ID | Gap | Why it blocks adoption | Follow-on task |
|---|---|---|---|
| G1 | Install is `pip install -e .` from a clone | Users expect a one-line install, not a developer checkout | TASK-008 |
| G2 | Two public remotes (`holodeck` and `holodeck-runtime`) | Confuses contributors and install docs | TASK-007 |
| G3 | Agent connection is “call raw HTTP yourself” | Tools will not integrate without a stable contract and adapter | TASK-009, TASK-010 |
| G4 | No MCP / SDK / agent protocol surface | Primary 2026 connection path for IDEs and agents | TASK-010 |
| G5 | Policy is advisory, not enforced | Users will over-trust `.holodeck/policy.json` as a sandbox | TASK-011 |
| G6 | stdlib HTTP server is the local daemon | Fine for alpha; polish/expectations gap for a shipped tool | TASK-012 |
| G7 | Coordination hardening unfinished | Concurrent claims can still race; trust-critical for multi-agent use | TASK-001 … TASK-006 |

## Delivery order (after hardening)

7. Unify the public repository identity and contributor entrypoint.
8. Publish an installable package with documented install paths.
9. Version and document a small stable HTTP API contract.
10. Ship a first-class MCP (or equivalent) agent adapter over that API.
11. Document policy as advisory and state the enforcement boundary explicitly.
12. Evaluate local daemon HTTP polish only if install/API friction remains.

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
