# 11. Integrated end-to-end lifecycle

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 11. Integrated end-to-end lifecycle

The subsystems above must operate as one coherent lifecycle. Implementing them as independent dashboards would recreate the original problem: records without governance.

### 11.1 Workspace onboarding

1. Register workspace sources and repository revision.
1. Run workspace curator and produce a proposal.
1. Validate and approve binding instructions and project model.
1. Persist workspace-model revision, context modules, role profiles, source registry, and knowledge gaps.
### 11.2 Task definition

1. Create task with human intent and parent work link where known.
1. Run task curator.
1. Create Task Position, requirement candidates, risk classification, context plan, and reviewer/test recommendations.
1. Resolve or explicitly accept missing context and contradictions.
1. Approve requirements and test plan.
1. Pass Definition Gate.
### 11.3 Worker execution

1. Select worker role and compile immutable worker packet.
1. Pass Execution Gate.
1. Launch through the appropriate adapter.
1. Capture automatic trace and required worklog checkpoints.
1. Process context/permission expansion through structured requests.
1. Worker submits completion candidate and candidate revision.
1. Validate candidate against trace and pass Review Submission Gate.
### 11.4 Review and revision

1. Create role-specific review requests and Review Position Packets.
1. Reviewers perform independent-first review and create findings.
1. If blocking findings exist, create review_changes_requested state.
1. Worker responds per finding and creates a new candidate revision.
1. Reviewer re-evaluates exact changes and resolves, reopens, or escalates findings.
1. When required jurisdictions approve, pass Review Approval Gate.
### 11.5 Verification and acceptance

1. Run approved deterministic, independent, adversarial, and holdout tests.
1. Map evidence to every blocking requirement.
1. Evaluate unresolved risks, policy requirements, and human approvals.
1. Pass Verification and Acceptance Gates.
1. Emit final acceptance decision linked to exact packet, revision, evidence, and reviews.
### 11.6 Learning

1. Identify learning candidates from validated failures, decisions, review corrections, and recovery strategies.
1. Validate source evidence and determine the appropriate knowledge type.
1. Promote approved learning into versioned workspace modules, requirements, regression tests, or policies.
1. Mark superseded knowledge and affected context modules.
### 11.7 Integrated sequence

```text
Human / Task Curator
  -> TaskPosition + Requirements + TestPlan
Gate Engine
  -> Definition accepted
Context Compiler
  -> Worker Packet
Agent Adapter
  -> Worker Run + Trace + Worklog
Worker
  -> CompletionCandidate + CandidateRevision
Review Service
  -> Findings
Worker
  -> FindingResponses + New CandidateRevision
Review Service
  -> Resolutions / Escalations
Verification Service
  -> Evidence + Requirement Coverage
Gate Engine
  -> AcceptanceDecision
Learning Service
  -> Validated Knowledge Candidates
```

### 11.8 Failure paths

| Failure | Required response |
| --- | --- |
| Missing task meaning or requirements | Block Definition Gate and create missing-context records. |
| Agent interruption | Create interrupted-run summary and recovery task/context. |
| Unsupported completion claim | Reject submission and request correction or stronger evidence. |
| Reviewer finds task-definition gap | Create scope-correction request; do not silently expand work. |
| Persistent worker-reviewer disagreement | Escalate according to role jurisdiction and risk. |
| Verification failure | Create findings/change request and regression-learning candidate. |
| Knowledge contradiction | Mark disputed; keep branches explicit until resolved. |
