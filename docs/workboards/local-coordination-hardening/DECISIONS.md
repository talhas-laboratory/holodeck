# Decisions

Record durable decisions here.

## 2026-07-22 — Local-only correctness release

- Keep zero runtime dependencies and SQLite as the single local authority.
- Make concurrency, data integrity, path identity, and lifecycle semantics reliable before networked agents or enforcement features.
- Bind to loopback by default; non-loopback operation requires an explicit insecure opt-in until authentication exists.
- Treat claims as logical repository-relative POSIX paths. Filesystem-aware symlink and case handling require a later repository-observation contract.
- Scope task IDs to a workspace.

## 2026-07-23 — OSS adoption follows hardening

- Keep Python + SQLite for the open-source local install goal; do not rewrite or move to Postgres for adoption.
- Append OSS packaging and integration work as TASK-007 … TASK-012 on this board after TASK-001 … TASK-006.
- Gap report of record: `docs/plans/2026-07-23-oss-adoption-gaps.md`.
- Prefer PyPI + documented API + first MCP adapter over language/runtime changes.
- Policy remains advisory until a later enforcement-adapter milestone; TASK-011 must make that explicit before launch messaging.

## 2026-07-23 — Elegance and modularity

- Project direction is recorded in root `AGENTS.md`: elegant solutions at each stage; modular boundaries so infrastructure can change quickly.

## 2026-07-23 — TASK-011 advisory policy boundary

- Policy decisions are advisory metadata, not runtime authorization or enforcement.
- Holodeck does not currently intercept, authorize, or block repository writes, network access, deployments, or other actions named in `.holodeck/policy.json`.
- Enforcement becomes in scope only with a tool or adapter mediation point plus an auditable approval and evidence model; disclosure must remain explicit until then.

## 2026-07-23 — TASK-008 package identity and licensing

- Holodeck is dual-licensed under `MIT OR Apache-2.0`; both complete license texts ship with source and wheel distributions.
- The public PyPI distribution is `holodeck-control-plane`, because the shorter `holodeck` distribution name is already occupied. Users invoke `holodeck`; Python imports use `holodeck`.
- Do not upload a release without explicit owner approval.

## 2026-07-23 — TASK-001 implementation decisions

- **SQLite connection defaults** (applied in `_connect()` and reused by all store operations):
  - `PRAGMA foreign_keys = ON`
  - `PRAGMA journal_mode = WAL`
  - `PRAGMA busy_timeout = 5000` (milliseconds)
- **Claim acquisition transaction:** `BEGIN IMMEDIATE` → read active claims → validate overlap → insert run + claims → `COMMIT`. Roll back on any failure.
- **Contention handling:** on `SQLITE_BUSY` / lock timeout after `busy_timeout`, raise `ContentionError` from `holodeck.errors`. TASK-005 maps this to HTTP `503`.
- **Overlap in TASK-001 (interim):** split stored paths on `/`, drop empty segments, compare as component tuples for equality and prefix overlap. Do **not** resolve `.` / `..`, reject absolutes, or normalize trailing slashes yet — TASK-003 owns full canonicalization.
- **Out of scope for TASK-001:** schema migrations, path grammar enforcement, lifecycle state machines, HTTP error mapping changes.

## 2026-07-23 — TASK-002 implementation decisions

- **Migration vehicle:** in-package numbered Python migrations in `holodeck/migrations.py` (or `holodeck/migrations/`), plus a small `migrate.py` runner. No Alembic, no SQL-file-only runner.
- **Ledger table:** `schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)`.
- **Application rules:** on every `Store` connect, run pending migrations in ascending version order inside a transaction; record each version once; migrations must be idempotent-safe when re-run logic is needed for tests.
- **Bootstrap:**
  - **Legacy baseline** = schema exactly as created today in `store.py` (`tasks.task_id` globally unique, `claims` without `run_id` column, `complete_run` uses JSON `LIKE`).
  - **Migration `001_relational_integrity`:** create ledger if missing; on legacy DB add `claims.run_id`, composite task identity, FKs, indexes, and status `CHECK` constraints; backfill `claims.run_id` from legacy JSON payloads; replace release query to use `run_id` column only.
  - **Fresh DB:** same migration creates the full current schema in relational form (no separate inline `CREATE TABLE` script after this lands).
- **Task identity:** replace global `tasks.task_id` primary key with composite unique `(workspace_id, task_id)`. `runs` references `(workspace_id, task_id)`.
- **Relational ownership:** `claims.run_id` is a real column, indexed, FK → `runs.run_id`. `complete_run` releases `WHERE run_id = ? AND status = 'active'` only.
- **Status `CHECK` constraints (domains only; transitions in TASK-004):**
  - `claims.status`: `active`, `released`
  - `runs.status`: `active`, `completed`, `failed`, `cancelled`
  - `tasks.status`: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`, `cancelled`
- **Out of scope for TASK-002:** backup/import/export, transition validation, path canonicalization.

## 2026-07-23 — TASK-003 implementation decisions

- **Path model:** logical repository-relative POSIX paths as normalized component tuples. No filesystem access, no symlink resolution, no case-folding.
- **Normalization rules:**
  - Reject: absolute paths (`/…`, `C:\…`), backslashes, empty/whitespace-only input, any `..` segment, `.` segments used only for traversal (collapse `.`; reject unresolved `..`).
  - Strip trailing `/`; collapse repeated `/`; trim surrounding whitespace before parse.
  - `.` alone means repository root, stored as an **empty component tuple** `()`.
  - `src/` → `("src",)`; `src/api.py` → `("src", "api.py")`.
- **Overlap:** two paths conflict if one component tuple is a prefix of the other (including equal). Replaces interim string/`startswith` logic from TASK-001.
- **Artifact roots:**
  - Default `["."]` means the whole repository (root tuple).
  - Empty `artifact_roots` rejects all claims.
  - A claim is valid only if it is equal to or a descendant of at least one normalized artifact root.
- **`scope_out`:**
  - Normalize `scope_out` entries with the same grammar.
  - Reject a claim if it is equal to, an ancestor of, or a descendant of any `scope_out` path (component-prefix intersection).
  - Example: `scope_out = ["src/vendor"]` rejects claims `src`, `src/vendor`, and `src/vendor/foo`.
- **Storage:** persist the canonical string form derived from the tuple (POSIX `/` join; root stored as `.`).
- **Unicode:** normalize each path segment with Unicode NFC so equivalent composed/decomposed spellings share one identity. Case-folding and symlink resolution remain out of scope.
- **Module home:** `holodeck/paths.py` (pure functions + domain errors). Store calls validator on `begin_run` and workspace boundary updates.
- **Out of scope for TASK-003:** symlink/case behavior, repository observation adapter, lifecycle rules.

## 2026-07-23 — TASK-004 implementation decisions

- **Module home:** `holodeck/lifecycle.py` — status sets, transition maps, validators only (no I/O).
- **Task status domain:** `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`, `cancelled`.
- **Run status domain:** `active`, `completed`, `failed`, `cancelled`.
- **Task transitions** (illegal transitions raise `ValidationError`; no DB write):

| From | Allowed to |
|------|------------|
| `backlog` | `ready`, `blocked`, `cancelled` |
| `ready` | `backlog`, `in-progress`, `blocked`, `cancelled` |
| `in-progress` | `ready`, `review`, `blocked`, `cancelled` |
| `review` | `in-progress`, `done`, `blocked`, `cancelled` |
| `blocked` | `backlog`, `ready`, `in-progress`, `review`, `cancelled` |
| `done` | _(none — terminal)_ |
| `cancelled` | _(none — terminal)_ |

- **Task create:** `status` defaults to `backlog`. If provided, it must be in the task domain (any value above, including `done`/`cancelled` for import compatibility). No transition check on create.
- **Run transitions:**

| From | Allowed to |
|------|------------|
| `active` | `completed`, `failed`, `cancelled` |
| `completed` | _(none — terminal)_ |
| `failed` | _(none — terminal)_ |
| `cancelled` | _(none — terminal)_ |

- **`begin_run` rules:**
  - Creates a run with `status = active`.
  - Rejects if the task is `done` or `cancelled`.
  - Rejects if the task does not exist in the workspace.
- **`complete_run` rules:**
  - Allowed only when run is `active`.
  - Outcome `status` must be one of `completed`, `failed`, `cancelled` (default `completed` when omitted — preserves current happy path).
  - Second completion attempt on a terminal run is rejected with no mutation.
  - Claim release remains atomic and uses `run_id` from TASK-002.
- **Compatibility:** existing default flows (`task` created as `backlog`, run completed as `completed`) remain valid without client changes.
- **Out of scope for TASK-004:** queued-run scheduling, approval workflows, auto task status changes when a run starts/ends.

## 2026-07-23 — TASK-005 implementation decisions

- **Request parsing:** mutations require `Content-Type: application/json`, explicit `Content-Length`, max body `65536` bytes, and a JSON object payload.
- **HTTP mapping:** `NotFoundError` → 404, `ConflictError` → 409, `ValidationError` → 422, `ContentionError` → 503, malformed JSON/media/body → 400/413/415 via `http_request.py`.
- **Identifiers:** URL path IDs must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`.
- **Binding:** loopback hosts (`127.0.0.1`, `localhost`, `::1`) are allowed by default; other binds require `--insecure-bind` (Docker uses this flag explicitly).
- **Server limits:** `HolodeckHTTPServer` applies a 30s socket timeout, caps concurrent request threads at 64, and returns HTTP 503 when at capacity before handler work starts.

## 2026-07-23 — TASK-002 follow-up (migration 002)

- **`tasks.workspace_id` FK** to `workspaces(workspace_id)`.
- **Claim safeguards:** partial unique index on active `(workspace_id, path)`; trigger rejects claims whose `workspace_id`/`task_id` do not match the referenced run.
- **List validation:** `validate_string_list()` rejects string-shaped list fields, requires list elements to already be strings, and bounds list size/length (see `holodeck/validation.py`).
- **Text fields:** `validate_text_field()` bounds scalar strings such as title, goal, intent, and summary.
- **Migration 002:** before the active-path unique index, normalize claim paths, release invalid legacy paths, release duplicate active claims (keep earliest), and fail active runs that lose all claims during reconciliation.
- **Task updates:** `update_task` uses `BEGIN IMMEDIATE` plus compare-and-swap on `status`.

## 2026-07-23 — Review fixes for TASK-001..006

- **Migrations:** apply each version inside an explicit `BEGIN IMMEDIATE`/`COMMIT` with `ROLLBACK` on failure; legacy upgrades rename tables and rebuild without `executescript` auto-commit. Unknown legacy statuses coerce to safe domain defaults (`task→backlog`, `run→active`, `claim→released`) before insert.
- **Integrity:** SQLite unique/FK violations map to `ConflictError` (HTTP 409), including duplicate workspace/task IDs.
- **Identifiers:** `workspace_id` / explicit `task_id` validated with the same URL-safe pattern used by HTTP path params (`holodeck/ids.py`).
- **Artifact roots:** omitted roots default to `["."]`; explicit `[]` is preserved and rejects all claims.
- **Paths:** reject Windows drive-letter absolutes (`C:/…`) as well as `/…` and backslashes.

## 2026-07-23 — Migration reconciliation follow-up

- **Legacy overlap policy:** after canonicalizing active claims, migration `002` keeps the earliest claim by `created_at`, then `claim_id`, within each workspace. It releases every later claim that has component-path overlap with an already kept claim.
- **Run payload consistency:** a run is synchronized whenever migration changes or releases any of its claims; an active run with no remaining active claims becomes `failed`.

## 2026-07-23 — Follow-on task verification standard

- **Invariant over example:** verification must prove the product rule, not just one happy-path spelling of it.
- **Boundary consistency:** when data crosses storage, HTTP, CLI, package, container, or adapter boundaries, tests compare the externally visible result with the authoritative state.
- **Completion discipline:** a residual risk that violates an acceptance criterion or the track guarantee blocks `done`; external publication or repository disposition needs explicit owner approval.

## 2026-07-23 — TASK-007 canonical repository

- **Canonical repository:** `talhas-laboratory/holodeck` is the sole public repository and the only `origin` push destination.
- **Legacy repository name:** GitHub resolves the former repository URL to the canonical repository. It is not an independent resource to archive; archiving it would archive the canonical repository, so the redirect is retained as the safe archive/redirect outcome.

## 2026-07-23 — TASK-006 implementation decisions

- **Image inputs:** copy only `pyproject.toml`, `README.md`, and `src/`; exclude dev artifacts via `.dockerignore`.
- **Runtime user:** container runs as `holodeck` (uid 10001) with `/data` owned for SQLite writes.
- **Compose:** loopback port bind, `read_only` root filesystem, `tmpfs` for `/tmp`, `no-new-privileges`, `cap_drop: [ALL]`.
- **Base image:** pin to `python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d`.
- **Verification:** `pip install -e ".[dev]"`, `pytest`, and `./scripts/verify_release.sh`; GitHub Actions workflow `.github/workflows/verify.yml`.
