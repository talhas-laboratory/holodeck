# Persistent codebase factual graph and context-compilation design

**Status:** Approved planning baseline
**Milestones:** M2 factual workspace intelligence; M3 context and mission compilation
**Implementation baseline:** cumulative M2 review PR #5 at `23a69594878a8f6609d4a3b1d239bf1d10c0de52`

## Decision

Holodeck will maintain a persistent, revision-scoped factual representation of
each bound repository. Holodeck owns the canonical fact schema, provenance,
freshness, permissions, and query semantics. Replaceable extractor adapters
produce candidate observations from code.

M2 persists only evidence-backed repository facts. M3 uses those facts,
approved workspace knowledge, and the task origin to produce a small,
role-specific context packet. Task-local interpretations remain labelled
hypotheses and do not silently become permanent repository truth.

```text
fixed repository revision
  -> extractor adapter
  -> normalized factual observations
  -> immutable graph snapshot in SQLite
  -> bounded factual queries
  -> M3 task-local analysis
  -> immutable context packet
  -> Codex, Claude Code, or another planning harness
```

## Why this shape

Research supports structural graphs for repository localization and
dependency-aware planning, while also showing that broad or stale context can
reduce task success. The graph is therefore an internal evidence and navigation
layer, not a large prompt.

The implementation must prove incremental value against ordinary agent search
and cheap repository heuristics. Graph completeness is not itself a product
success metric.

Primary research used for this decision:

- [LocAgent](https://aclanthology.org/2025.acl-long.426/) — graph-guided code
  localization and downstream issue-resolution evidence.
- [CodePlan](https://arxiv.org/abs/2309.12499) — dependency/change-impact
  planning for multi-file repository transformations.
- [ContextBench](https://arxiv.org/abs/2602.05892) — context
  recall/precision, over-retrieval, and utilization in coding agents.
- [SWE-Explore](https://arxiv.org/abs/2606.07297) — repository exploration
  coverage/ranking and downstream repair behavior.
- [AGENTS.md evaluation](https://arxiv.org/abs/2602.11988) — repository
  overviews and context-file cost/quality effects.
- [Stale repository context study](https://arxiv.org/abs/2605.14478) —
  current-versus-obsolete retrieval effects.
- [GitNexus license](https://github.com/nxpatterns/gitnexus/blob/main/LICENSE)
  — current PolyForm Noncommercial terms.

## Authority and ownership

| Authority | Owns |
| --- | --- |
| Git and CI | Repository revisions, executable code, artifacts, and verification results. |
| Extractor adapter | Best-effort observation of code structure at one fixed revision. |
| Holodeck M2 | Normalized facts, snapshot identity, provenance, freshness, bounded query semantics, and workspace readiness effects. |
| Holodeck M3 | Task interpretation, query plans, relevance decisions, hypotheses, context packets, and mission proposals. |
| Coding harness | Technical plan proposals, implementation, exploration, and worker-authored claims. |

Extractor output is data. It cannot grant instruction authority, approve an
interpretation, raise workspace readiness by itself, or authorize execution.

## Scope

### M2 initial factual scope

- Repository, directory, file, module, class, function, method, test, manifest,
  configuration, migration, schema object, and API entry-point entities.
- `contains`, `defines`, `imports`, `calls`, `inherits`, `reads`, `writes`,
  `exposes`, `handles`, `tests`, `configures`, and `migrates` relations.
- Exact repository binding, commit, file, source span, content hash, extractor
  identity/version/configuration, and observation method.
- Immutable snapshots with one explicitly active snapshot per repository
  binding and workspace.
- Full extraction first; incremental refresh reuses unchanged facts only after
  equivalence is proven.
- Bounded traversal and impact-neighborhood queries.
- Cheap high-recall sentinels for changed public interfaces, schemas,
  migrations, tests, configuration, and sensitive paths/symbols.

### Deferred

- General data-flow, control-flow, taint, or vulnerability analysis.
- Runtime topology inferred from static code.
- Vector search or a graph-database dependency.
- Permanent purpose, lifecycle, product, security, or reliability maps.
- Cross-repository graphs.
- Model-generated facts.
- M3 relevance ranking, summarization, hypotheses, context packets, missions,
  requirements, tests, execution, or acceptance.

## Canonical record model

The records follow existing M1/M2 conventions: tenant coupling, opaque IDs,
UTC timestamps, immutable observations, explicit schema versions, application
services, additive SQLite migrations, domain events, and stable error reasons.

### RepositoryGraphSnapshot

```text
snapshot_id
tenant_id
workspace_object_id
repository_binding_id
repository_revision             # immutable commit/object identifier
status                          # building | active | failed | superseded
base_snapshot_id?
extraction_run_id
coverage_status                 # complete | partial | unknown
coverage_notes[]
entity_count
relation_count
created_by_actor_id
created_at
activated_at?
schema_version
```

A branch name is not a repository revision. A failed or partial build never
replaces the active snapshot without an explicit, policy-checked decision.

### RepositoryExtractionRun

```text
extraction_run_id
snapshot_id
provider_key
provider_version
provider_schema_version
configuration_hash
requested_revision
actual_revision
started_at
completed_at?
status                          # running | succeeded | partial | failed
diagnostics[]
limits
```

The actual revision must equal the requested revision before activation.

### CodeEntityFact

```text
entity_fact_id
tenant_id
workspace_object_id
repository_binding_id
entity_key                      # deterministic within repository/revision
entity_kind
language?
qualified_name?
repository_relative_path
start_line?
start_column?
end_line?
end_column?
source_id
source_observation_id
content_hash?
observation_method              # direct_parse | statically_resolved |
                                # tool_inferred | runtime_observed
extractor_native_id?
created_at
schema_version
```

Renames or moves create new factual identities unless a deterministic provider
can prove continuity. Holodeck does not infer conceptual sameness from names.

### CodeRelationFact

```text
relation_fact_id
tenant_id
workspace_object_id
repository_binding_id
relation_kind
source_entity_fact_id
target_entity_fact_id
evidence_source_id
evidence_observation_id
evidence_span?
observation_method
confidence?                     # required only for tool-inferred relations
qualifiers
created_at
schema_version
```

Directly parsed or statically resolved relations do not receive artificial
model confidence. Tool-inferred relations must expose confidence and
limitations.

### Snapshot membership

Entity and relation facts are immutable. Snapshot-membership tables associate
facts with snapshots. Unchanged facts may be reused by a later snapshot only
when their source observation, normalized payload, and relation endpoints are
identical. This avoids copying all facts while preserving exact historical
reconstruction.

## Extractor boundary

The domain must not import Tree-sitter, GitNexus, Joern, LadybugDB, or provider
schemas. The application layer depends on a port similar to:

```text
RepositoryExtractor
  describe_capabilities() -> ExtractorCapabilities
  extract(ExtractionRequest) -> ExtractionResult

ExtractionRequest
  repository_path
  repository_binding_id
  requested_revision
  language_allowlist
  path_includes
  path_excludes
  limits
  base_snapshot_descriptor?
  changed_paths?

ExtractionResult
  actual_revision
  provider_descriptor
  candidate_entities[]
  candidate_relations[]
  diagnostics[]
  coverage
```

Candidates are normalized and validated before persistence. Unknown entity or
relation types are rejected or recorded as diagnostics; they are not silently
stored as generic facts.

## Provider decision

The initial production-compatible adapter is Python-first and uses the Python
standard-library AST plus deterministic repository metadata. It establishes
the contract and test fixtures without introducing a license or runtime
dependency.

GitNexus is a research and compatibility reference, not the default production
dependency. Its current PolyForm Noncommercial license does not permit assuming
commercial product use. It may become an adapter only after an explicit license
decision. Tree-sitter is the preferred later route for broader language
coverage behind the same port. Joern may later supply explicitly labelled deep
analysis facts.

Provider evaluation must record:

- license and redistribution compatibility;
- supported languages and relation coverage;
- deterministic output at a pinned version;
- fixed-revision operation and stale-index detection;
- structured export without requiring prompt generation;
- offline/privacy behavior;
- installation and runtime footprint;
- failure, timeout, and partial-coverage reporting;
- extraction accuracy on Holodeck-owned fixtures;
- full and incremental extraction latency.

## Ingestion and activation

1. Resolve an active repository binding and immutable commit.
2. Register or refresh repository files as `WorkspaceSource` observations.
3. Create a `building` snapshot and extraction run.
4. Run the adapter under explicit path, file-size, entity, relation, and time
   limits.
5. Normalize candidate records and reject cross-tenant, cross-workspace,
   absolute-path, unknown-source, invalid-span, dangling-edge, and revision
   mismatches.
6. Persist facts and snapshot memberships in a transaction.
7. Validate counts, referential integrity, coverage, and requested/actual
   revision equality.
8. Activate the snapshot atomically. The previous active snapshot remains
   queryable and becomes superseded only after successful activation.
9. Emit durable success, partial, failure, and activation events.

No partially written graph may become queryable as the active graph.

## Refresh and invalidation

A repository revision change creates a new snapshot. Refresh never mutates the
old snapshot.

- Obtain changed paths from a repository adapter or an explicit trusted input.
- Re-extract changed files and any deterministically affected resolution
  neighborhood.
- Reuse an old fact only when its full normalized identity and evidence
  observation remain unchanged.
- If the adapter cannot establish the affected neighborhood, perform a full
  extraction or mark coverage partial. Never claim incremental completeness
  from absence of discovered edges.
- Mark context modules that depend on changed source observations stale through
  the existing M2 propagation seam.
- Keep historical snapshots and observations queryable for run
  reproducibility.

## Bounded query surface

M2 exposes factual operations, not arbitrary Cypher or SQL:

```text
get_active_snapshot
get_snapshot
find_entities
get_entity
get_neighbors
traverse_paths
get_change_neighborhood
get_sources_for_facts
compare_snapshots
```

Every query requires tenant/workspace/repository scope and explicit budgets:
allowed entity/relation kinds, direction, maximum depth, result count, and
visited-node count. Results include selection paths, source observations,
coverage limitations, and truncation reasons.

M2 does not label a missing path as proof that no dependency exists.

## Cheap sentinels

Sentinels are deterministic warnings used as a baseline and defence in depth:

- path and ownership tags;
- public API or exported-symbol changes;
- schema and migration changes;
- test-to-implementation association;
- configuration and dependency-manifest changes;
- sensitive symbol/path lists;
- missing or partial extraction coverage.

Sentinels can activate investigation. They cannot clear a risk dimension.

## M3 use of the graph

M3 performs:

```text
task origin
  -> typed task contract and readiness state
  -> task decomposition
  -> seed entity resolution
  -> bounded factual query plan
  -> trust/freshness/authority filtering
  -> optional task-local hypotheses
  -> compact immutable context packet
  -> mission proposal and planning-harness handoff
```

Interpretive probe results use:

```text
activated    # evidence supports relevance
cleared      # explicit bounded evidence supports absence
unresolved   # evidence is insufficient
conflicted   # evidence supports incompatible conclusions
```

`No evidence found` means `unresolved`, not `cleared`.

The first experimental probes are:

- data, state, and external contracts;
- authority, security, and control.

Each hypothesis records premises, factual paths, source revisions, inference
type, confidence, alternatives, verification obligation, and invalidation
conditions. Hypotheses are task-local unless a separate human-governed process
promotes them to approved workspace knowledge.

## Failure behavior

- Missing checkout or revision: reject before creating an active snapshot.
- Provider unavailable: retain the current active snapshot and record failure.
- Timeout/resource limit: record partial diagnostics; do not silently claim
  completeness.
- Malformed provider output: reject the affected candidate and fail activation
  when referential integrity or revision identity is compromised.
- Changed repository during extraction: reject because actual revision differs.
- Duplicate command: return the same snapshot/run result through M1
  idempotency.
- Concurrent refresh: serialize activation per repository binding and ensure
  only one snapshot becomes active.
- Unsupported language: record explicit coverage gaps and reduce readiness.
- Query budget exhausted: return deterministic truncation and omission reasons.

## Verification strategy

### Deterministic fixture repositories

Maintain a small Python fixture containing:

- modules, classes, functions, imports, calls, and inheritance;
- direct and aliased imports;
- data reads/writes;
- API entry point and handler;
- schema/migration;
- unit and integration tests;
- configuration and manifest files;
- an intentionally unresolved dynamic call;
- two commits with known changed and unchanged neighborhoods.

Golden expectations are typed facts and paths, not provider-native output.

### Required test layers

- Domain validation and deterministic-key tests.
- Extractor contract tests reusable by every provider.
- SQLite migration, tenant-coupling, immutability, and index tests.
- Atomic ingestion, failure, replay, and concurrent-activation tests.
- Full-versus-incremental equivalence tests.
- Bounded traversal and truncation tests.
- Historical snapshot reconstruction tests.
- M2 onboarding/refresh integration tests.
- M3 compact-packet and provenance tests.
- Agent-quality benchmark.

## Quality benchmark

Use the same model, coding harness, repository revision, task, tool permissions,
token budget, and retry count across these arms:

```text
A. ordinary agent search
B. A + typed task intake and cheap sentinels
C. B + bounded factual-graph retrieval
D. C + task-local interpretive probes
```

Evaluate local edits, cross-module behavior, schema/API changes,
authorization/security changes, and caching/retry/concurrency changes.

Primary metrics:

- accepted patch rate;
- consequential affected-component recall;
- regression and high-risk false-negative rate;
- required-test and invariant coverage.

Secondary metrics:

- context precision/recall/F1;
- context actually used in the patch;
- tokens, latency, and tool calls;
- extraction and refresh cost;
- stale-fact rate;
- human-review burden.

The graph is justified only if C beats B on cross-component quality without
unacceptable cost. Interpretive probes proceed beyond experiment only if D
beats C. Exact promotion thresholds must be recorded before running the
benchmark so results cannot move the gate after the fact.

## Milestone boundary and order

### M2

1. Factual graph contracts and fixture.
2. Extractor port and provider/license assessment.
3. SQLite persistence and query indexes.
4. Python reference extractor.
5. Snapshot ingestion and activation.
6. Incremental refresh and invalidation.
7. Bounded queries and sentinels.
8. End-to-end factual-graph acceptance and M3 handoff.

### M3

1. Typed task contracts and readiness.
2. Task positioning, decomposition, and ambiguity records.
3. Seed resolution and bounded context planning.
4. Task-local interpretive probe interface.
5. Deterministic context packet compilation.
6. Mission proposal and authority gates.
7. Context expansion.
8. Planning-harness handoff.
9. Comparative agent-quality benchmark and M4 handoff.

## Completion definition

The solution is complete only when:

- an exact repository revision produces a reproducible factual snapshot;
- historical snapshots remain queryable;
- a changed revision refreshes safely without exposing partial state;
- queries return bounded evidence paths with provenance and limitations;
- identical M3 inputs compile the same immutable packet hash;
- untrusted repository content cannot become instructions;
- ambiguity and missing evidence remain visible;
- the executor can request a linked context expansion;
- benchmark results show which richer stages improve quality over the cheaper
  baseline;
- unsupported or non-improving interpretive machinery remains disabled.
