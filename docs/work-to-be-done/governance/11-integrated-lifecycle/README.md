# Integrated end-to-end lifecycle

## Governing flow

`Human/Curator -> TaskPosition + Requirements + TestPlan -> Gate Engine -> Context Compiler -> Agent Adapter -> Worker Trace + Worklog -> CompletionCandidate + CandidateRevision -> Review -> Finding responses/new revisions -> Verification evidence -> Gate Engine AcceptanceDecision -> Validated learning`

## Lifecycle stages

1. Onboard sources, curate/approve workspace model and modules.
2. Define task, curate position/requirements/context/test recommendations, resolve gaps, pass Definition Gate.
3. Compile worker packet, pass Execution Gate, launch, trace, handle expansion/permission requests, submit candidate, pass Review Submission Gate.
4. Run jurisdictional review and revision cycles until Review Approval Gate.
5. Run deterministic, independent, adversarial, and holdout verification; map evidence to requirements; evaluate policy/risk/approvals; emit an AcceptanceDecision.
6. Validate and promote learning with provenance; mark superseded knowledge and stale modules.

## Required failure handling

Missing meaning blocks definition. Interruptions create recovery summaries. Unsupported claims are rejected. Scope gaps create correction requests. Persistent disagreement escalates. Verification failures create findings and regression-learning candidates. Knowledge contradictions remain disputed until resolved.
