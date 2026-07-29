# Tasks

| id | status | owner | title | depends on |
| --- | --- | --- | --- | --- |
| `M2-000` | done | codex | Establish M2 entry readiness and workspace-model contract | M1-025 artifact |
| `M2-001` | done | cursor | Define collaboration boundary and intake scenario specification | M2-000 |
| `M2-002` | done | cursor | Add collaboration bindings, external actor mappings, and durable event receipts | M2-001 |
| `M2-003` | done | cursor | Record task origins and source-thread context through the M1 application seam | M2-001, M2-002 |
| `M2-004` | done | cursor | Add transactional outbound collaboration-message delivery | M2-001, M2-002 |
| `M2-005` | done | cursor | Define repository/project and collaboration-location workspace bindings | M2-002 |
| `M2-006` | ready | unassigned | Implement explainable workspace discovery and eligibility evaluation | M2-003, M2-005 |
| `M2-007` | backlog | unassigned | Implement reversible workspace-genesis proposals and human decision flow | M2-003, M2-005, M2-006 |
| `M2-008` | backlog | unassigned | Implement a provider-neutral in-memory adapter test harness | M2-001–M2-007 |
| `M2-009` | backlog | unassigned | Implement the first Buzz adapter behind the neutral collaboration boundary | M2-001–M2-008 |
| `M2-010` | backlog | unassigned | Prove end-to-end authenticated intake, replay recovery, and correlated status | M2-002–M2-009 |
| `M2-012` | backlog | unassigned | Define workspace intelligence records and contracts | M2-000 |
| `M2-013` | backlog | unassigned | Persist workspace intelligence and expose governed application operations | M2-012 |
| `M2-014` | backlog | unassigned | Implement repository/source discovery and trust classification | M2-012, M2-013 |
| `M2-015` | backlog | unassigned | Implement workspace curation, approval, activation, and readiness | M2-012–M2-014 |
| `M2-016` | backlog | unassigned | Implement refresh, stale propagation, and intelligence query APIs | M2-013–M2-015 |
| `M2-017` | backlog | unassigned | Prove workspace onboarding and refresh scenarios | M2-012–M2-016 |
| `M2-011` | backlog | unassigned | Publish M2 contracts and M3 handoff | M2-010, M2-017 |

Status values: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`.
