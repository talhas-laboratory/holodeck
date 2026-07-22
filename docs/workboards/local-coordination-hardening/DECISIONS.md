# Decisions

Record durable decisions here.

## 2026-07-22 — Local-only correctness release

- Keep zero runtime dependencies and SQLite as the single local authority.
- Make concurrency, data integrity, path identity, and lifecycle semantics reliable before networked agents or enforcement features.
- Bind to loopback by default; non-loopback operation requires an explicit insecure opt-in until authentication exists.
- Treat claims as logical repository-relative POSIX paths. Filesystem-aware symlink and case handling require a later repository-observation contract.
- Scope task IDs to a workspace.
