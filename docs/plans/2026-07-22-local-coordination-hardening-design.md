# Local coordination hardening design

## Release intent

Make Holodeck a reliable local-only traffic controller for multiple agents in one repository. The release remains dependency-free at runtime and does not claim authentication, tool enforcement, repository observation, or evidence capture.

## Decisions

- SQLite remains the authority. Claim acquisition is one explicit `BEGIN IMMEDIATE` transaction: read active claims, validate candidates, insert the run and claims, commit. Database contention is bounded and reported rather than silently racing.
- Claims use a canonical, logical repository-relative POSIX path. Absolute paths, backslash ambiguity, traversal outside the repository, and invalid root/exclusion intersections are rejected. Component comparison, not raw string prefixing, defines overlap.
- Database evolution uses numbered migrations and a migration ledger. Every connection enables foreign keys, WAL, and a busy timeout. Claims gain `run_id`; records critical to coordination gain foreign keys, indexes, and constrained statuses.
- Task identifiers are scoped to their workspace. Run and task lifecycle transitions are validated by explicit state machines.
- The HTTP server applies bounded, typed request validation and stable errors. It remains loopback-only by default and requires an explicit insecure opt-in for other interfaces.

## Delivery order

1. Serialize claim acquisition and prove the race is closed.
2. Add migrations and relational claim ownership.
3. Canonicalize claims and enforce workspace path boundaries.
4. Enforce lifecycle and identity contracts.
5. Harden request parsing, errors, and binding.
6. Harden the container and establish automated release checks.
7. Unify public OSS repository identity.
8. Ship a PyPI-installable package.
9. Version and document the stable HTTP API.
10. Ship the first MCP agent adapter.
11. Clarify advisory policy boundary in user-facing docs.
12. Evaluate local daemon HTTP polish only if concrete friction remains.

Steps 7–12 are the OSS adoption track detailed in `docs/plans/2026-07-23-oss-adoption-gaps.md`.

## Release acceptance

- Competing concurrent claims cannot both succeed.
- Equivalent, escaping, excluded, and out-of-root paths are rejected correctly.
- Existing databases upgrade without losing records, and completion releases only claims owned by its run.
- Invalid state transitions and malformed requests receive deterministic HTTP errors.
- The container runs as a non-root user and its build context excludes local runtime and repository artifacts.

## Explicitly deferred

Authenticated principals, approvals with enforcement adapters, filesystem isolation, tool-call auditing, verification evidence, stale-run recovery, backup/import/export, a full threat model, language rewrites, and Postgres/MySQL remain subsequent milestones. OSS packaging and agent-adapter work is tracked as TASK-007 … TASK-012 in `docs/plans/2026-07-23-oss-adoption-gaps.md`, not deferred indefinitely.
