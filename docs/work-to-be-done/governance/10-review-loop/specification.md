# 10. Structured reviewer-worker feedback system

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 10. Structured reviewer-worker feedback system

The review system must be a closed, revision-oriented protocol. Reviewers create structured findings against an exact candidate revision. Workers respond to each finding, submit a new revision, and the reviewer explicitly resolves, reopens, modifies, withdraws, or escalates each finding.

### 10.1 Reviewer alignment with the grand scheme

A reviewer cannot reliably judge a diff from task text alone. The reviewer must receive a Review Position Packet derived from the work graph and task position.

```text
ReviewPositionPacket
  workspace_purpose
  active_milestone
  parent_outcome
  parent_capability
  parent_feature
  task_purpose
  affected_users[]
  task_scope[]
  non_goals[]
  upstream_dependencies[]
  downstream_consumers[]
  parallel_tasks[]
  project_constraints[]
  affected_invariants[]
  requirements[]
  risk_classification
  reviewer_role_and_jurisdiction
  exact_candidate_revision
  diff_from_base
  evidence_index
  worker_completion_candidate
  relevant_architecture_and_decisions[]
```

### 10.2 Independent-first review sequence

1. Independent requirement review. Reviewer inspects purpose, requirements, exact revision, diff, tests, and architecture before reading the worker’s detailed narrative.
1. Trace and worklog inspection. Reviewer then checks decisions, failures, and recovery against observed evidence.
1. Adversarial verification. Reviewer or linked verifier runs targeted checks within its jurisdiction.
1. Structured findings. Reviewer records actionable, evidence-linked findings with explicit acceptance conditions.
This order reduces anchoring on the worker’s explanation and helps reviewers challenge the outcome rather than confirm the implementation story.

### 10.3 Immutable candidate revisions

```text
CandidateRevision
  id
  task_id
  run_id
  parent_revision_id
  repository_base_revision
  repository_result_revision
  diff_artifact
  files_changed[]
  completion_candidate_id
  created_at
  immutable_hash
```

Each review request targets one candidate revision. A worker response creates a new revision; it never mutates the revision already reviewed.

### 10.4 Review request and review

```text
ReviewRequest
  id
  task_id
  candidate_revision_id
  reviewer_role_revision
  requested_jurisdiction[]
  review_position_packet_id
  required_by_gate
  status

Review
  id
  review_request_id
  reviewer_actor_id
  reviewer_role_revision
  reviewed_revision_id
  summary
  overall_recommendation
  confidence
  findings[]
  submitted_at
```

### 10.5 Structured finding

```text
Finding
  id
  review_id
  candidate_revision_id
  category
  finding_type             # implementation, scope_gap, suggestion, new_task
  severity                 # blocker, critical, major, minor, suggestion
  blocking                 # boolean constrained by reviewer jurisdiction
  status                   # open, addressed, resolved, reopened, withdrawn,
                           # accepted_risk, superseded, escalated, waived
  title
  observation
  impact
  related_requirements[]
  related_invariants[]
  anchors[]
  evidence_refs[]
  required_change
  acceptance_conditions[]
  confidence
  created_at
```

### 10.6 Anchors

Line-only comments are fragile. A finding may use multiple anchors:

- Repository commit and diff hunk.
- File and line range.
- Function, class, symbol, or semantic component.
- Requirement or invariant.
- Test, evidence artifact, log, or runtime event.
- Architecture decision or context module.
- Task, feature, or capability node.
### 10.7 Worker response

```text
FindingResponse
  id
  finding_id
  worker_actor_id
  response_revision_id
  response_type            # fixed, partially_fixed, disagree,
                           # cannot_reproduce, blocked, requires_scope_change,
                           # accepted_risk_request
  explanation
  changes[]                # file/symbol/commit anchors
  evidence_refs[]
  requirement_impact[]
  remaining_risk
  proposed_disposition
  submitted_at
```

```text
Required behavior
The worker must respond to every open blocking finding individually. “Fixed review comments” is not an acceptable aggregate response.
```

### 10.8 Re-review

- The reviewer receives the complete new candidate revision and the delta from the previously reviewed revision.
- The reviewer sees each worker response and linked evidence.
- The reviewer checks whether the requested acceptance conditions are satisfied and whether new regressions were introduced.
- The reviewer explicitly resolves, reopens, modifies, withdraws, or escalates each finding.
- If a later revision changes the same semantic area, previously resolved findings MAY be marked for regression review.
### 10.9 Disagreement and escalation

The reviewer is not automatically correct. Workers may disagree, but must provide evidence and explain the requirement or constraint that supports the disagreement.

```text
Review cycle 1
  worker fixes or responds
Review cycle 2
  reviewer resolves or restates the remaining issue precisely
Persistent disagreement
  -> architecture/product/security escalation according to jurisdiction
  -> human task owner or authorized decision-maker when required
```

Final finding states must be explicit: resolved, withdrawn, accepted risk, superseded, escalated, or waived by authorized actor. A finding must not disappear because a conversation ended.

### 10.10 Reviewer roles and jurisdiction

| Reviewer role | Primary questions | Typical blocking jurisdiction |
| --- | --- | --- |
| Product Reviewer | Does the work solve the intended user/system problem and match feature purpose? | User-visible or product-intent requirements. |
| Architecture Reviewer | Does it preserve system boundaries, dependencies, invariants, and long-term coherence? | Architectural constraints and cross-component risk. |
| Security Reviewer | Can authority, data, or trust boundaries be bypassed? | Security and access-control requirements. |
| Test Reviewer | Do tests and oracles actually prove the requirements? | Evidence sufficiency and test integrity. |
| Implementation Reviewer | Is the implementation correct, maintainable, and consistent with repository conventions? | Implementation-quality requirements. |
| Operations/Migration Reviewer | Is deployment, compatibility, recovery, and rollback safe? | Operational and migration gates. |

### 10.11 Review is not final acceptance

A reviewer recommends a disposition within its jurisdiction. Final acceptance remains a gate-engine decision combining review, deterministic checks, independent verification, policy, and required human approval.

### 10.12 Minimum APIs

```text
POST /candidate-revisions
POST /candidate-revisions/{id}/review-requests
GET  /review-requests/{id}/position-packet
POST /review-requests/{id}/reviews
POST /findings/{id}/responses
POST /candidate-revisions/{id}/resubmit
POST /findings/{id}/resolve
POST /findings/{id}/reopen
POST /findings/{id}/escalate
GET  /tasks/{task}/review-history
```

### 10.13 Acceptance criteria

- Every review targets an immutable candidate revision.
- Every finding has at least one semantic or evidence anchor and an explicit requested outcome.
- Workers can answer each finding with fixes, evidence, disagreement, or escalation requests.
- Reviewers receive task purpose and project-position context before evaluating the change.
- Blocking findings cannot disappear without an explicit terminal disposition.
- Reviewer blocking authority is constrained by role jurisdiction.
