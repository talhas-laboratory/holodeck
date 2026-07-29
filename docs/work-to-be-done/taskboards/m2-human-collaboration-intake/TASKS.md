# Tasks

| id | status | owner | title | depends on |
| --- | --- | --- | --- | --- |
| `M2-000` | done | codex | Establish M2 entry readiness and workspace-model contract | M1-025 artifact |
| `M2-001` | done | cursor | Define collaboration boundary and intake scenario specification | M2-000 |
| `M2-002` | done | cursor | Add collaboration bindings, external actor mappings, and durable event receipts | M2-001 |
| `M2-003` | done | cursor | Record task origins and source-thread context through the M1 application seam | M2-001, M2-002 |
| `M2-004` | done | cursor | Add transactional outbound collaboration-message delivery | M2-001, M2-002 |
| `M2-005` | done | cursor | Define repository/project and collaboration-location workspace bindings | M2-002 |
| `M2-006` | done | cursor | Implement explainable workspace discovery and eligibility evaluation | M2-003, M2-005 |
| `M2-007` | done | cursor | Implement reversible workspace-genesis proposals and human decision flow | M2-003, M2-005, M2-006 |
| `M2-008` | done | cursor | Implement a provider-neutral in-memory adapter test harness | M2-001–M2-007 |
| `M2-009` | blocked | unassigned | Implement the first Buzz adapter behind the neutral collaboration boundary | M2-001–M2-008 |
| `M2-010` | done | cursor | Prove end-to-end authenticated intake, replay recovery, and correlated status | M2-002–M2-008 |
| `M2-012` | done | cursor | Define workspace intelligence records and contracts | M2-000 |
| `M2-013` | done | cursor | Persist workspace intelligence and expose governed application operations | M2-012 |
| `M2-014` | done | cursor | Implement repository/source discovery and trust classification | M2-012, M2-013 |
| `M2-015` | done | cursor | Implement workspace curation, approval, activation, and readiness | M2-012–M2-014 |
| `M2-016` | done | cursor | Implement refresh, stale propagation, and intelligence query APIs | M2-013–M2-015 |
| `M2-017` | ready | unassigned | Prove workspace onboarding and refresh scenarios | M2-012–M2-016 |
| `M2-018` | done | cursor | Preserve conversation context manifests on task origins | M2-003, M2-008 |
| `M2-019` | ready | unassigned | Define factual code-graph contracts and golden fixture | M2-016 |
| `M2-020` | backlog | unassigned | Establish extractor port and provider assessment | M2-019 |
| `M2-021` | backlog | unassigned | Persist immutable code-graph snapshots in SQLite | M2-019 |
| `M2-022` | backlog | unassigned | Implement the Python reference extractor | M2-019, M2-020 |
| `M2-023` | backlog | unassigned | Ingest, validate, and activate factual graph snapshots | M2-021, M2-022 |
| `M2-024` | backlog | unassigned | Implement safe incremental graph refresh and invalidation | M2-023 |
| `M2-025` | backlog | unassigned | Expose bounded factual queries and high-recall sentinels | M2-023, M2-024 |
| `M2-026` | backlog | unassigned | Prove factual graph acceptance and publish the M3 handoff | M2-017, M2-023–M2-025 |
| `M2-011` | backlog | unassigned | Publish M2 contracts and M3 handoff | M2-010, M2-017, M2-018, M2-026 |

Status values: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`.
