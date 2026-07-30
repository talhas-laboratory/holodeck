# Vocabulary ledger

Terms introduced in this channel. Plain-language anchor first; technical term is what he'll recognize in docs and code over time.

_Reuse the technical term directly in later explanations unless he signals confusion._

| Plain language | Technical term | Context introduced | Date |
|----------------|----------------|-------------------|------|
| The structure/shape of stored data — what fields exist and how records relate | **schema** | TASK-002 | 2026-07-23 |
| A safe, versioned way to change that structure without breaking existing data | **migration** | TASK-002 | 2026-07-23 |
| A record of which structural changes have already been applied | **migration ledger** / `schema_migrations` table | TASK-002 | 2026-07-23 |
| Rules that force links between records to be real (e.g. a claim must point to an existing run) | **relational integrity** / **foreign keys** | TASK-002 | 2026-07-23 |
| A generic JSON blob holding record details instead of dedicated columns | **payload** | TASK-002 | 2026-07-23 |
| Searching inside text instead of looking up a dedicated field | **LIKE query** (text pattern match) | TASK-002 | 2026-07-23 |
| A dedicated, indexed field for direct lookup | **column** | TASK-002 | 2026-07-23 |
| Identity scoped inside a boundary (unique per workspace, not globally) | **composite key** / workspace-scoped identity | TASK-002 | 2026-07-23 |
| Allowed states enforced at the data layer (e.g. only `active` or `released`) | **CHECK constraint** | TASK-002 | 2026-07-23 |
| Copying data from old shape into new fields during a structural change | **backfill** | TASK-002 | 2026-07-23 |
