# 4. Workspace, task, and on-demand curation

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 4. Workspace, task, and on-demand curation

Curator intelligence is valuable because it can understand semantic relevance and discover missing context. It is dangerous if it becomes an unrestricted prompt authority. The implementation must therefore constrain curator outputs to structured proposals that deterministic services validate and persist.

### 4.1 Curator roles

| Curator | Runs when | Primary outputs |
| --- | --- | --- |
| Workspace Curator | Onboarding, explicit refresh, or major source change. | Workspace model, knowledge map, modules, source classifications, role proposals, contradictions, gaps. |
| Task Curator | Task creation or material task revision. | Task position, requirement candidates, risks, context modules, role recommendations, verification needs, missing information. |
| On-demand Curator | Worker/reviewer requests more context, stale context is detected, or unexpected dependencies emerge. | Targeted source discovery, context expansion proposal, gap record, or escalation. |

### 4.2 What curators own and do not own

| Curator MAY | Curator MUST NOT |
| --- | --- |
| Discover relevant sources and rank them. | Directly overwrite approved workspace instructions. |
| Propose requirements, risks, roles, and tests. | Mark its own inferred requirements as final without the required approval path. |
| Detect contradictions, ambiguity, and missing knowledge. | Hide disagreement or uncertainty. |
| Generate summaries with provenance and confidence. | Treat untrusted repository content as instruction authority. |
| Recommend context additions and exclusions. | Construct an unreviewable hidden system prompt. |
| Recommend escalation or block readiness due to missing context. | Decide final task acceptance. |

### 4.3 Workspace curation workflow

1. Inventory registered sources and repository structure.
1. Classify sources by trust, sensitivity, freshness, and ownership.
1. Infer project purpose, users, capabilities, architecture, principles, terminology, and non-goals.
1. Extract candidate context modules and role profiles.
1. Detect contradictions, undocumented invariants, and missing policies.
1. Produce a structured proposal with source links and confidence.
1. Apply deterministic schema and safety validation.
1. Route binding changes for human approval.
1. Persist the approved workspace-model revision and emit refresh events.
### 4.4 Task curation workflow

1. Interpret the requested task in relation to workspace purpose and active milestone.
1. Locate the parent capability, feature, and related work.
1. Identify users, system actors, and scenarios affected by the task.
1. Determine scope, non-goals, upstream dependencies, downstream consumers, and parallel tasks.
1. Propose requirements, invariants, risks, failure consequences, and evidence expectations.
1. Select context modules and additional sources by role.
1. Recommend worker and reviewer profiles and required jurisdictions.
1. Identify ambiguity or missing context that prevents readiness.
1. Create a versioned Task Position and Task Context Plan.
### 4.5 Structured curator output

```text
TaskCurationProposal
  task_id
  based_on_workspace_revision
  interpretation_summary
  parent_links[]
  affected_users[]
  purpose
  contributes_to[]
  scope[]
  non_goals[]
  dependencies[]
  downstream_consumers[]
  requirement_candidates[]
  risk_classification
  failure_consequences[]
  context_module_selections[]
  source_selections[]
  recommended_worker_role
  recommended_reviewer_roles[]
  required_evidence[]
  missing_context[]
  contradictions[]
  confidence
  provenance[]
```

### 4.6 Curator reliability controls

- Use structured output schemas and reject free-form-only curator responses.
- Run deterministic validation for missing required fields, unknown identifiers, forbidden trust escalation, and incompatible role recommendations.
- Store the curator model/version and exact source revisions.
- Require explicit “unknown” or “not found” values rather than invented facts.
- Allow users to compare proposed and approved workspace/task models.
- Measure curator quality through downstream context gaps, requirement changes, reviewer corrections, and escaped failures.
### 4.7 Acceptance criteria

- Task creation can produce a complete, inspectable task-position proposal without launching a worker.
- The curator can report that a task is not ready due to missing product or architectural context.
- Curator output cannot independently change binding instructions or acceptance status.
- On-demand curation creates a new context-expansion revision rather than altering an active run packet.
- Every source selection has a reason and provenance link.
