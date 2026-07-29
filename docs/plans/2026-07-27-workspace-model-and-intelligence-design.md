# Workspace model and intelligence design

**Status:** Implementation-ready contract (M2-013–M2-016 shipped: persistence, discovery, curation/activation, freshness/query; onboarding E2E deferred to M2-017)
**Milestones:** M2 workspace intelligence and genesis; M3 context compilation
**Companion tasks:** M2-012 contracts; M2-013 persistence; M2-014 discovery/trust; M2-015 curation/activation
**Contract package:** `holodeck_governance.domain.workspace.intelligence`

## Decision

Define the full durable workspace model now, but populate it progressively.
A workspace may be incomplete. Unknown, disputed, stale, and inferred content
are explicit states, never gaps filled with invented certainty.

A workspace is a governed, versioned representation of a project or bounded
work domain. It is not a repository URL, directory, chat channel, or hidden
prompt.

## Product boundary

| System | Owns |
| --- | --- |
| Collaboration platform | Signed messages, external identity, membership, threads, notifications. |
| Repository and CI | Source revisions, code, artifacts, tests, and merge controls. |
| Holodeck workspace | Project semantics, source registry, authority, readiness, provenance, and approved context. |
| Coding harness | Technical exploration, planning proposals, code changes, and worker-authored claims. |

Repository text, tickets, logs, and generated summaries are data, not
instructions, unless an authorized human explicitly promotes them. A repository
or collaboration location may be bound to a workspace but is never itself the
workspace.

## Record model

All records use M1 conventions: tenant ownership, opaque IDs, UTC timestamps,
provenance, immutable revisions, content hashes, commands, events, and outbox
delivery. Core links are typed relations, not JSON references.

### Workspace

The stable container and lifecycle anchor.

~~~
Workspace
  workspace_id
  tenant_id
  display_name
  lifecycle_state          # proposed | active | suspended | archived
  current_model_revision_id
  current_readiness_assessment_id
  created_by_actor_id
  created_at
~~~

The Workspace contains no mutable project meaning. Material changes create a
new model revision.

### WorkspaceModelRevision

The approved or proposed project model. Each section is source-linked and is
individually marked confirmed, proposed, unknown, disputed, or superseded.

~~~
WorkspaceModelRevision
  model_revision_id
  workspace_id
  revision
  status                   # proposed | approved | superseded
  based_on_revision_id
  intent_seed_ref
  section_summary_hashes
  provenance_refs[]
  confidence_summary
  created_by_actor_id
  approved_by_actor_id?
  created_at
  approved_at?
~~~

A model revision has seven required sections.

#### 1. Identity and purpose

- Project/system name and concise description.
- Purpose, intended outcomes, current maturity, and primary value.
- Scope boundary: what belongs in this workspace and what does not.
- Explicit non-goals and forbidden outcomes.
- Risk posture and maximum autonomy level.

The initial human intent seed must include purpose, primary users, important
risks, non-goals, and decisions Holodeck must not make automatically.

#### 2. Stakeholders, actors, and authority

- Stakeholders, owners, operators, and affected users.
- System actors, goals, likely mistakes, and failure consequences.
- Workspace-local role assignments and delegated authority references.
- Escalation contacts and decisions reserved to humans.
- Authorized collaboration locations.

This section references M1 Actor, RoleProfile, RoleAssignment, and
DelegatedGrant records. It does not duplicate their authority logic.

#### 3. Product and domain model

- Capabilities, features, service promises, and user journeys.
- Domain concepts, entities, states, and business rules.
- Quality priorities and trade-off preferences.
- Critical invariants and known failure consequences.

This is project understanding, not task-specific requirements. Requirements
remain M4 work.

#### 4. Architecture and system map

- Components and their responsibilities.
- Interfaces, APIs, events, data flow, and dependency boundaries.
- Data stores, schemas, migrations, and integrity expectations.
- External systems and integration boundaries.
- Repository layout, languages, build/test tooling, CI, deployment, and
  runtime topology.

Each architecture item declares whether it is observed, an approved reference,
or a generated inference, with sources and confidence.

#### 5. Engineering principles and constraints

- Approved engineering principles and architecture decisions.
- Compatibility, API, migration, dependency, performance, security, privacy,
  and accessibility constraints.
- Testing, quality, operational, release, and rollback expectations.
- Allowed and prohibited workspace-level change categories.

Only approved instruction-authority content can bind future agents. Repository
content and generated summaries stay references.

#### 6. Domain language

- Canonical terms and definitions.
- Accepted aliases.
- Prohibited or ambiguous terms and preferred replacements.
- References establishing the terminology.

#### 7. Decisions, contradictions, and gaps

- Accepted and rejected decisions with rationale and source revision.
- Contradictory sources and interpretations, retained separately.
- Open questions, missing documentation, and explicitly unknown facts.
- Impact, urgency, owner, and readiness consequence for every gap.

No curator or agent may silently resolve disagreement or invent an answer.

### RepositoryBinding

Associates a repository with a workspace while preserving repository authority.

~~~
RepositoryBinding
  binding_id
  workspace_id
  provider
  external_repository_id
  canonical_locator
  default_branch
  binding_status           # proposed | active | retired
  external_reference_id
  provenance_ref
~~~

M2 records repository identity and observed revisions. M5 later chooses a fixed
execution revision and creates an execution workspace.

### CollaborationLocationBinding

Associates a project, community, channel, or thread with a workspace.

~~~
CollaborationLocationBinding
  binding_id
  workspace_id
  endpoint_id
  location_kind
  external_location_id
  intake_policy_id
  status
  provenance_ref
~~~

It supports explainable workspace selection; it never makes the external
conversation the system of record.

### WorkspaceSource

The registry for every input used to form workspace knowledge.

~~~
WorkspaceSource
  source_id
  workspace_id
  source_type              # repository_file | document | API | human_input |
                           # task_history | runtime_observation | test_result
  locator
  observed_revision        # commit, hash, document revision, event ID
  content_hash?
  owner
  trust_class              # instruction_authority | authoritative_reference |
                           # trusted_observation | ordinary_reference |
                           # untrusted_reference | generated_interpretation
  sensitivity
  refresh_policy
  observed_at
  stale_status
  instruction_authority    # requires explicit approval
  provenance_ref
~~~

Generated interpretations may be sources, but can never become instructions by
themselves. A source update marks only modules that depend on it stale.

### ContextItem

A small, inspectable fact, claim, instruction, or unknown.

~~~
ContextItem
  item_id
  workspace_id
  item_type                # source_fact | approved_instruction | workspace_rule |
                           # generated_summary | assumption | open_question |
                           # conflict | decision | runtime_observation |
                           # incident_learning
  statement
  source_refs[]
  trust_class
  confidence?
  freshness
  validation_status        # unverified | supported | verified | disputed |
                           # superseded | archived
  applicability
  conflicts_with[]
  created_by_actor_id
  approved_by_actor_id?
~~~

Observed facts do not receive artificial confidence values; generated
interpretations do.

### ContextModule

A versioned, bounded set of context items and sources for one concern. Every
module has a purpose, applicability rule, freshness status, source links, and
approval status.

| Module | Contents |
| --- | --- |
| core-principles | Purpose, non-goals, binding principles, quality priorities. |
| product-and-users | Stakeholders, users, capabilities, and failure consequences. |
| architecture | Components, interfaces, data flow, dependencies, and boundaries. |
| data-and-persistence | Data model, migrations, retention, and integrity expectations. |
| testing-and-verification | Test conventions, tooling, test layers, and evidence expectations. |
| security-and-authority | Trust boundaries, permissions, protected assets, escalation. |
| operations-and-release | Deployment, monitoring, rollback, incident, and support expectations. |
| domain-language | Canonical vocabulary and definitions. |
| decisions-and-history | Approved decisions, relevant incidents, validated learning. |

Modules can be absent or incomplete. That must lower readiness; it must not
cause automatic model-generated filler.

### KnowledgeGap, Contradiction, WorkspaceDecision

~~~
KnowledgeGap
  gap_id, workspace_id, question, affected_sections[], impact,
  risk_if_unresolved, owner_actor_id?, status, resolution_ref?

Contradiction
  contradiction_id, workspace_id, claim_refs[], description,
  impact, status, resolution_ref?

WorkspaceDecision
  decision_id, workspace_id, subject_revision, outcome,
  rationale, signed_source_event_ref?, authorized_actor_id, decided_at
~~~

### WorkspaceReadinessAssessment

Readiness is a versioned, evidence-backed decision. It records the model
revision, dimensions checked, gaps, policy basis, evaluator result, and actor.

| Level | Meaning | Permitted capability |
| --- | --- | --- |
| 0 — Uninterpreted | Repository registered; no reliable project model. | Browsing and summarization only. |
| 1 — Discovered | Technical structure observed; semantic context weak. | Explanation and limited suggestions. |
| 2 — Contextualized | Purpose, users, capabilities, major constraints known. | Planning and supervised implementation proposals. |
| 3 — Governed | Authority, invariants, risk policy, and roles defined. | Bounded controlled execution. |
| 4 — Verifiable | Reliable environment, oracles, and independent tests exist. | Autonomous acceptance for approved risk classes. |
| 5 — Operationally assured | Operations, rollback, monitoring, and learning integrated. | Highly autonomous lanes where policy permits. |

## Progressive onboarding

~~~
intent seed + repository binding
  -> source registration and discovery
  -> proposed model, modules, and gaps
  -> deterministic validation
  -> human approval of binding content
  -> active workspace + readiness assessment
  -> selective refresh
~~~

1. An authorized human supplies purpose, users, risks, non-goals, and decision
   boundaries.
2. Read-only discovery inventories repository structure, manifests, tests, CI,
   documentation, schemas, configuration, ownership, and connected sources.
3. A workspace curator proposes the model, source classifications, modules,
   roles, gaps, contradictions, confidence, and readiness.
4. Deterministic validation rejects missing IDs, trust escalation, invalid
   bindings, and schema violations.
5. A human approves purpose/non-goal, risk-posture, authority, and
   instruction-authority changes. Policy may permit automatic approval of
   low-risk descriptive metadata.
6. Holodeck activates the approved model revision and readiness assessment.
7. Source changes, explicit human changes, missing context, and repeated
   failures produce targeted refresh proposals; they never mutate active run
   context silently.

## M2 and M3 boundary

M2 creates and maintains workspace models, sources, bindings, context modules,
gaps, and readiness. It also receives authenticated work requests and selects
or proposes a workspace.

M3 takes a task origin, workspace model revision, and role contract. It creates
the task-specific position and scope, selects relevant sources and modules,
resolves or escalates task-specific ambiguity, and compiles an immutable
role-specific context packet.

M3 asks Codex, Claude Code, or another harness for a technical plan. Holodeck
does not attempt to replace the harness's implementation reasoning.

## Commands, APIs, and events

M2 operations must use the M1 command/application seam, then emit durable
events and any required outbox messages transactionally.

~~~
POST /workspaces
POST /workspaces/{id}/intelligence/onboard
POST /workspaces/{id}/intelligence/refresh
GET  /workspaces/{id}/model?revision=...
GET  /workspaces/{id}/sources
POST /workspaces/{id}/sources
GET  /workspaces/{id}/context-modules
POST /workspaces/{id}/context-modules/{module}/approve
GET  /workspaces/{id}/knowledge-gaps
POST /workspaces/{id}/knowledge-gaps/{gap}/resolve
GET  /workspaces/{id}/readiness
POST /workspace-genesis-proposals
POST /workspace-genesis-proposals/{id}/decide
~~~

Initial events:

~~~
workspace.intelligence.onboarding_requested
workspace.model.proposed
workspace.model.approved
workspace.source.registered
workspace.source.stale
workspace.context_module.stale
workspace.knowledge_gap.created
workspace.readiness.assessed
workspace.genesis.proposed
workspace.genesis.decided
~~~

## Implementation and verification

Keep M1's domain/application/storage/adapter separation. Add domain contracts,
application operations, storage protocols, and additive persistence rather than
overloading M1's thin WorkspaceRecord and SourceRecord.

The M2 board needs explicit packets for:

1. workspace model, sources, context items/modules, gaps, decisions, and
   readiness contracts;
2. additive persistence and command/application operations;
3. source/repository discovery and trust classification;
4. curator proposal, validation, approval, and activation;
5. selective freshness propagation and intelligence query APIs;
6. onboarding and refresh acceptance scenarios.

Completion evidence must prove:

- Onboarding creates a versioned model, source registry, modules, gaps, and a
  provenance report.
- Untrusted repository content cannot become approved instruction without an
  authorized promotion.
- Generated summaries identify exact source revisions and confidence.
- A source change stales only dependent modules.
- Contradictions remain visible until a recorded resolution.
- Old approved model revisions remain queryable.
- Readiness cannot exceed the evidence and approved authority available.
- M1 tenant isolation, revisioning, idempotency, authorization, and outbox
  guarantees continue to hold.

## Non-goals

- Replacing a coding harness's planning ability.
- Granting repository, network, secret, deployment, or approval authority from
  repository content.
- A vector database, graph database, or unrestricted autonomous curation in the
  initial implementation.
- A mutable hidden workspace prompt.
- Execution worktrees or agent launching, which are M5.
- Task-specific missions, requirements, test plans, or acceptance decisions,
  which are M3, M4, and M6.
