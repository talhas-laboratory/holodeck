# Tasks

| id | status | owner | title | depends on |
| --- | --- | --- | --- | --- |
| `M1-026` | done | implementation-agent | Establish fresh-builder baseline and compatibility contract | — |
| `M1-001` | done | implementation-agent | Define kernel vocabulary and module contracts | M1-026 |
| `M1-031` | done | implementation-agent | Define domain-error, reason-code, and event-schema catalogs | M1-001 |
| `M1-002` | done | implementation-agent | Write governance test specification | M1-001, M1-031 |
| `M1-003` | done | implementation-agent | Add default-local tenant and tenant isolation | M1-001, M1-002 |
| `M1-004` | done | implementation-agent | Add opaque IDs and shared governance metadata | M1-001, M1-002 |
| `M1-005` | done | implementation-agent | Add immutable object revisions and heads | M1-003, M1-004 |
| `M1-006` | done | implementation-agent | Define legacy-import mapping and provenance | M1-003–M1-005 |
| `M1-007` | done | implementation-agent | Add provenance, trust, and validation records | M1-003–M1-005 |
| `M1-008` | done | implementation-agent | Add generic external references | M1-003, M1-004, M1-007 |
| `M1-027` | done | implementation-agent | Add typed workspace, source, intent, mission, and task records | M1-003–M1-005, M1-007, M1-008 |
| `M1-028` | done | implementation-agent | Add typed requirement, test-plan, run, artifact, and evidence records | M1-005, M1-007, M1-008, M1-027 |
| `M1-029` | done | implementation-agent | Add typed review, approval, decision, and escalation records | M1-005, M1-007, M1-008, M1-010 |
| `M1-009` | done | implementation-agent | Add typed traceability edges | M1-003–M1-005, M1-007, M1-008, M1-027–M1-029 |
| `M1-010` | done | implementation-agent | Add actors and versioned role profiles | M1-003–M1-005 |
| `M1-011` | done | implementation-agent | Add role assignments and jurisdiction checks | M1-010 |
| `M1-012` | done | implementation-agent | Add delegated grants, expiry, and revocation | M1-005, M1-010, M1-011 |
| `M1-030` | done | implementation-agent | Implement repositories and unit-of-work transaction boundary | M1-003–M1-005, M1-008, M1-027–M1-029 |
| `M1-013` | done | implementation-agent | Add versioned task and run transition definitions | M1-005, M1-010–M1-012, M1-027, M1-028 |
| `M1-014` | done | implementation-agent | Add command envelopes and immutable receipts | M1-005, M1-010–M1-013, M1-030, M1-031 |
| `M1-015` | done | implementation-agent | Add command idempotency and concurrency control | M1-014 |
| `M1-016` | done | implementation-agent | Add typed primitive registry and composition | M1-007, M1-012–M1-015 |
| `M1-017` | done | implementation-agent | Add evaluation snapshots and results | M1-016 |
| `M1-018` | done | implementation-agent | Add policy bindings, precedence, and activation | M1-012, M1-016, M1-017 |
| `M1-019` | done | implementation-agent | Add tenant-sequenced domain event ledger | M1-014–M1-018, M1-031 |
| `M1-020` | done | implementation-agent | Add atomic event-to-outbox creation | M1-019, M1-030 |
| `M1-021` | done | implementation-agent | Add outbox leasing, retry, and dead-letter escalation | M1-020 |
| `M1-022` | done | implementation-agent | Add decision reconstruction query services | M1-008, M1-009, M1-017–M1-021, M1-027–M1-030 |
| `M1-023` | done | implementation-agent | Execute legacy migration and compatibility tests | M1-006, M1-013–M1-022 |
| `M1-032` | done | implementation-agent | Enforce tenant-coupled object ownership | M1-003, M1-005, M1-023 |
| `M1-033` | done | implementation-agent | Tenant-coupled authority references | M1-010, M1-011, M1-012, M1-032 |
| `M1-034` | done | implementation-agent | Govern authority-record issuance | M1-012, M1-033 |
| `M1-024` | review | implementation-agent | Prove all integrated governance scenarios | M1-003–M1-023, M1-027–M1-034 |
| `M1-025` | review | implementation-agent | Publish contracts, migration guide, and M2 handoff | M1-024 |

Status values: `backlog`, `ready`, `in-progress`, `review`, `blocked`, `done`.
No task may enter `done` without all gates in `GATES.md`.

Board note: **M1-034 done** (migration v10 authority issuance). **M1-024 and M1-025 remain in review**; milestone **not** accepted.
