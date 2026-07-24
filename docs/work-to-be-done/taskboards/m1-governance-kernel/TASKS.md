# Tasks

| id | status | owner | title | depends on |
| --- | --- | --- | --- | --- |
| `M1-026` | ready | unassigned | Establish fresh-builder baseline and compatibility contract | — |
| `M1-001` | backlog | unassigned | Define kernel vocabulary and module contracts | M1-026 |
| `M1-031` | backlog | unassigned | Define domain-error, reason-code, and event-schema catalogs | M1-001 |
| `M1-002` | backlog | unassigned | Write governance test specification | M1-001, M1-031 |
| `M1-003` | backlog | unassigned | Add default-local tenant and tenant isolation | M1-001, M1-002 |
| `M1-004` | backlog | unassigned | Add opaque IDs and shared governance metadata | M1-001, M1-002 |
| `M1-005` | backlog | unassigned | Add immutable object revisions and heads | M1-003, M1-004 |
| `M1-006` | backlog | unassigned | Define legacy-import mapping and provenance | M1-003–M1-005 |
| `M1-007` | backlog | unassigned | Add provenance, trust, and validation records | M1-003–M1-005 |
| `M1-008` | backlog | unassigned | Add generic external references | M1-003, M1-004, M1-007 |
| `M1-027` | backlog | unassigned | Add typed workspace, source, intent, mission, and task records | M1-003–M1-005, M1-007, M1-008 |
| `M1-028` | backlog | unassigned | Add typed requirement, test-plan, run, artifact, and evidence records | M1-005, M1-007, M1-008, M1-027 |
| `M1-029` | backlog | unassigned | Add typed review, approval, decision, and escalation records | M1-005, M1-007, M1-008, M1-010 |
| `M1-009` | backlog | unassigned | Add typed traceability edges | M1-003–M1-005, M1-007, M1-008, M1-027–M1-029 |
| `M1-010` | backlog | unassigned | Add actors and versioned role profiles | M1-003–M1-005 |
| `M1-011` | backlog | unassigned | Add role assignments and jurisdiction checks | M1-010 |
| `M1-012` | backlog | unassigned | Add delegated grants, expiry, and revocation | M1-005, M1-010, M1-011 |
| `M1-030` | backlog | unassigned | Implement repositories and unit-of-work transaction boundary | M1-003–M1-005, M1-008, M1-027–M1-029 |
| `M1-013` | backlog | unassigned | Add versioned task and run transition definitions | M1-005, M1-010–M1-012, M1-027, M1-028 |
| `M1-014` | backlog | unassigned | Add command envelopes and immutable receipts | M1-005, M1-010–M1-013, M1-030, M1-031 |
| `M1-015` | backlog | unassigned | Add command idempotency and concurrency control | M1-014 |
| `M1-016` | backlog | unassigned | Add typed primitive registry and composition | M1-007, M1-012–M1-015 |
| `M1-017` | backlog | unassigned | Add evaluation snapshots and results | M1-016 |
| `M1-018` | backlog | unassigned | Add policy bindings, precedence, and activation | M1-012, M1-016, M1-017 |
| `M1-019` | backlog | unassigned | Add tenant-sequenced domain event ledger | M1-014–M1-018, M1-031 |
| `M1-020` | backlog | unassigned | Add atomic event-to-outbox creation | M1-019, M1-030 |
| `M1-021` | backlog | unassigned | Add outbox leasing, retry, and dead-letter escalation | M1-020 |
| `M1-022` | backlog | unassigned | Add decision reconstruction query services | M1-008, M1-009, M1-017–M1-021, M1-027–M1-030 |
| `M1-023` | backlog | unassigned | Execute legacy migration and compatibility tests | M1-006, M1-013–M1-022 |
| `M1-024` | backlog | unassigned | Prove all integrated governance scenarios | M1-003–M1-023, M1-027–M1-031 |
| `M1-025` | backlog | unassigned | Publish contracts, migration guide, and M2 handoff | M1-024 |

Status values: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`.
No task may enter `done` without all gates in `GATES.md`.
