# Appendices

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## Appendix A — Canonical object inventory

| Object | Purpose |
| --- | --- |
| WorkspaceModel | Versioned project purpose, users, architecture, principles, terminology, constraints, gaps. |
| WorkspaceSource | Registered source with revision, trust, ownership, sensitivity, freshness, and module tags. |
| ContextModule | Reusable bounded knowledge and instruction unit. |
| RoleProfile | Versioned operational contract for worker, curator, reviewer, or verifier. |
| TaskPosition | Task location and meaning in the wider project. |
| Requirement | Structured obligation with scenarios, acceptance conditions, and evidence requirements. |
| TestPlan | Failure hypotheses, boundaries, oracles, layers, coverage, and pass policy. |
| ContextPacket | Immutable role-specific run context with provenance and hash. |
| ContextExpansionRequest | Structured request for additional context. |
| RunTraceEvent | Normalized observed action or result. |
| WorklogEvent | Agent-authored decision-relevant record linked to evidence. |
| CompletionCandidate | Worker submission for review and verification. |
| CandidateRevision | Immutable repository result revision. |
| ReviewRequest | Assignment of a revision to a reviewer role and jurisdiction. |
| Review | Reviewer assessment of one revision. |
| Finding | Structured actionable review item. |
| FindingResponse | Worker response tied to a new revision and evidence. |
| VerificationEvidence | Test, evaluator, runtime, or approval artifact. |
| AcceptanceDecision | Gate-owned final decision with reasons and evidence. |
| KnowledgeCandidate | Potential reusable learning awaiting validation/promotion. |
| KnowledgeRevision | Validated durable workspace knowledge. |

## Appendix B — Suggested event catalogue

- workspace.intelligence.onboarding_requested
- workspace.model.proposed
- workspace.model.approved
- workspace.context_module.stale
- workspace.knowledge_gap.created
- task.curation.requested
- task.position.created
- requirement.proposed
- requirement.approved
- gate.evaluation.completed
- context.packet.compiled
- context.expansion.requested
- run.started
- run.trace_event.recorded
- run.worklog_event.recorded
- run.interrupted
- completion_candidate.submitted
- candidate_revision.created
- review.requested
- review.finding.created
- review.finding.responded
- review.finding.resolved
- review.finding.escalated
- verification.started
- verification.evidence.recorded
- acceptance.decision.created
- knowledge_candidate.created
- knowledge.promoted
- knowledge.superseded
## Appendix C — Worked example: safe parallel agent execution task

This example demonstrates how the objects interact without prescribing the foundational implementation fix itself.

### C.1 Task position

```text
task: Improve exclusive work-surface coordination
parent_capability: Safe parallel agent execution
parent_feature: Work-surface claims
purpose: Prevent incompatible concurrent work while preserving useful parallelism
users:
  - worker agents
  - supervising developers
  - platform operators
contributes_to:
  - bounded autonomous execution
  - recoverable coordination
non_goals:
  - permanent code ownership
  - granting filesystem authority
upstream_dependencies:
  - workspace path model
  - run lifecycle
downstream_consumers:
  - agent launcher
  - dashboard
  - verification engine
```

### C.2 Requirement candidate

```text
requirement: Conflicting active ownership must be impossible
rationale: Parallel agents must not perform incompatible work on the same surface
scenarios:
  - two workers request the same surface
  - one worker requests a parent and another a child surface
  - a worker requests additional scope during execution
acceptance_conditions:
  - conflicting requests cannot both be active
  - rejected actor receives a machine-readable reason
  - non-conflicting work is not unnecessarily blocked
  - historical ownership remains auditable
required_evidence:
  - concurrency integration evidence
  - end-to-end adapter scenario
  - review of recovery behavior
```

### C.3 Reviewer finding and response

```text
finding:
  title: Implementation protects conflicts but blocks unrelated work
  type: implementation
  severity: blocker
  anchors:
    - requirement: preserve useful parallelism
    - component: work-surface acquisition
  required_change:
    Preserve exclusivity without unnecessary cross-workspace serialization
  acceptance:
    - conflicting requests remain exclusive
    - unrelated workspace operations continue independently

worker_response:
  type: fixed
  new_candidate_revision: REV-2
  changes:
    - scoped coordination to the relevant workspace operation
  evidence:
    - independent parallel-workspace test
  remaining_risk:
    - database writer throughput remains bounded under extreme load
```

### C.4 Learning promotion

```text
validated learning candidate:
  type: architecture principle
  statement: Safety mechanisms must preserve intended concurrency outside the protected conflict domain
  sources:
    - requirement
    - reviewer finding
    - independent test evidence
  promotion target:
    - workspace architecture context module
    - future concurrency test-plan template
```

## Appendix D — Implementation checklist

| Area | Completion check |
| --- | --- |
| Shared model | IDs, revisions, provenance, trust, actors, roles, evidence, events implemented |
| Workspace intelligence | Model, sources, modules, gaps, freshness, approvals implemented |
| Curators | Workspace/task/on-demand structured proposals with validation |
| Context compiler | Precedence, role packets, budgets, preview, hashing, expansion |
| Work graph | Purpose-to-task links and Task Position implemented |
| Requirements | Structured records, approval, traceability, gates |
| Tests | TestPlan, failure model, oracles, independent layers, coverage |
| Trace/worklog | Automatic trace, checkpoints, completion, interruption, validation |
| Adapters | Generic launcher, permissions, normalized telemetry, CI backstop |
| Review | Revisions, packets, findings, responses, re-review, escalation |
| Learning | Candidates, validation, promotion, supersession, retrieval |
| Integrated acceptance | End-to-end task passes all lifecycle stages with full audit reconstruction |

## Closing implementation directive

```text
Build the system around evidence and authority
Do not implement these improvements as disconnected prompt forms, dashboards, or agent personas. The implementation is correct only when purpose, requirements, context, execution, documentation, review, verification, acceptance, and learning are linked through enforceable lifecycle transitions and immutable evidence.
```
