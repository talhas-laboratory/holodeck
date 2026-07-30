# 6. Work graph, structured requirements, and gates

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 6. Work graph, structured requirements, and gates

Requirements cannot be generated reliably from code alone. They must derive from project purpose, users, feature intent, scenarios, risk, and surrounding work. Holodeck therefore needs a work graph that explains where each task sits in the larger system and a requirement model that turns meaning into testable obligations.

### 6.1 Work hierarchy

```text
Workspace Purpose
  -> Product Outcome / Milestone
      -> Capability / Workstream
          -> Feature
              -> Task
                  -> Requirement
                      -> Candidate Revision
                          -> Test / Evidence / Review / Decision
```

The implementation MAY store this in relational tables with typed edges; a graph database is not required. What matters is preserving typed, versioned relationships.

### 6.2 Task Position

Every task must have a compact, versioned record explaining its role in the grand scheme of work. This record is central to correct requirement generation and review.

```text
TaskPosition
  id
  revision
  task_id
  workspace_model_revision
  parent_outcome_id
  parent_capability_id
  parent_feature_id
  purpose
  affected_users[]
  contributes_to[]
  upstream_dependencies[]
  downstream_consumers[]
  parallel_related_tasks[]
  scope[]
  non_goals[]
  affected_invariants[]
  project_constraints[]
  current_milestone
  risk_classification
  failure_consequences[]
  provenance[]
```

### 6.3 Requirement object

```text
Requirement
  id
  revision
  task_id
  source_refs[]
  statement
  rationale
  type                    # behavior, invariant, constraint, quality, policy, compatibility
  priority
  severity_if_violated
  affected_users[]
  scenarios[]
  scope
  non_goals[]
  preconditions[]
  observable_outcomes[]
  acceptance_conditions[]
  verification_methods[]
  required_evidence[]
  approval_status
  validation_status
  supersedes[]
```

### 6.4 Requirement generation hierarchy

| Stage | Question answered | Primary context |
| --- | --- | --- |
| Purpose | Why does this project or feature exist? | Workspace purpose, users, product promise, non-goals. |
| Stakeholders and situations | Who depends on it and under what circumstances? | Roles, workflows, likely mistakes, operational situations. |
| Risks and consequences | What happens when it fails? | Security, business, user, operational, and recovery consequences. |
| Requirements and invariants | What must be observable or always true? | Approved intent, scenarios, constraints, and architecture. |
| Tests and evidence | What would demonstrate satisfaction or violation? | Requirement, failure model, interface, boundary, oracle, environment. |

### 6.5 Gate model

| Gate | Transition controlled | Minimum checks |
| --- | --- | --- |
| Definition Gate | draft -> ready | Purpose, task position, requirements, scenarios, scope, non-goals, risk, required evidence, unresolved questions. |
| Execution Gate | ready -> executable/run active | Context packet, exact revisions, role, permissions, environment, test plan, required approvals. |
| Review Submission Gate | worker active -> submitted_for_review | Candidate revision, completion candidate, trace availability, requirement mapping, claimed evidence, remaining risks. |
| Review Approval Gate | changes_requested/review -> review_approved | All blocking findings resolved or formally dispositioned within jurisdiction. |
| Verification Gate | review_approved -> verified | Required independent tests/evaluations pass and evidence coverage is complete. |
| Acceptance Gate | verified -> accepted | No unresolved critical findings, required human/policy decisions exist, record is complete. |
| Release Gate | accepted -> released | Release-specific checks, approvals, rollback and runtime conditions. |

### 6.6 State model

```text
draft
  -> definition_review
      -> blocked \| ready
ready
  -> in_progress
in_progress
  -> interrupted \| failed \| submitted_for_review
submitted_for_review
  -> review_changes_requested \| review_approved
review_changes_requested
  -> revision_in_progress -> resubmitted_for_review
review_approved
  -> verification
verification
  -> changes_required \| verified
verified
  -> accepted \| acceptance_blocked
accepted
  -> released \| archived
```

```text
Authority rule
Workers may request transitions such as submitted_for_review. Only the gate engine may finalize gated transitions such as review_approved, verified, accepted, or released.
```

### 6.7 Scope corrections and new-task proposals

Reviewers and test agents must not silently expand a task. Findings must distinguish implementation failure from missing or incorrect task definition.

| Finding type | Meaning | Disposition |
| --- | --- | --- |
| Implementation finding | The candidate fails an approved requirement. | Worker fixes or responds within the task. |
| Scope-gap finding | The approved task omitted necessary behavior or constraint. | Route to task owner/curator for requirement revision. |
| Improvement suggestion | Useful enhancement that is not required for acceptance. | Non-blocking; optionally create follow-up. |
| New-task proposal | Separate work outside current scope. | Create linked task; do not block unless current result is unsafe without it. |

### 6.8 Traceability

```text
Requirement
  -> implementing task and candidate revision
  -> tests and evidence
  -> review findings and responses
  -> verification decision
  -> acceptance decision
  -> promoted knowledge or regression protection
```

### 6.9 Acceptance criteria

- Every task prepared for execution has a Task Position revision.
- Every blocking requirement has explicit acceptance conditions and required evidence.
- The gate engine can explain exactly why a transition passed or failed.
- No reviewer or worker can silently redefine task scope.
- A requirement can be traced to evidence, review, and final acceptance.
