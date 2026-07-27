# Gate taxonomy

## Purpose

Holodeck must distinguish the question a gate is answering. A package that is
safe to assign is not necessarily complete; a completed task is not necessarily
an accepted mission; a mission accepted in one environment is not necessarily
ready for broad operational release.

```text
handoff readiness
→ task execution
→ task completion
→ mission / milestone acceptance
→ operational or release readiness
```

No gate may silently use evidence intended for another gate type.

## Gate types

| Gate | Governing question | Minimum evidence | Primary milestone |
| --- | --- | --- | --- |
| Handoff readiness | Can this role begin bounded work without hidden context or invention? | Scope, authority, decisions, dependencies, context selection, test oracle, escalation path. | M3–M5 |
| Task completion | Did this bounded change meet its stated contract? | Changed artifacts, required tests, negative-path checks, evidence, residual risks. | M4–M6 |
| Mission / milestone acceptance | Do composed task outputs satisfy the governed outcome and required evidence? | Requirement traceability, independent findings where required, gate decisions, reconstruction. | M6–M7 |
| Operational / release readiness | Can the system be safely operated, recovered, and trusted in its target environment? | Clean candidate, compatibility matrix, recovery evidence, observability, runbooks, accepted risks. | M8 |

## Handoff-readiness gate

This is the gate derived from the M1 fresh-builder audit. It asks whether a
fresh competent agent can find the authoritative sources, understand the
direction and boundary, follow the dependency path, implement the assigned
work, and verify it without relying on an unavailable conversation.

It must not claim that the task or mission is already complete.

## Completion and acceptance safeguards

Later gates should require the following where risk warrants it:

- Evidence is internally consistent, versioned, and tied to the candidate
  revision or environment.
- A high-impact change is not certified only by its implementing agent.
- Residual risks are classified as accepted limitation, deferred capability,
  operational concern, required-invariant violation, or unknown. The final two
  block acceptance.
- Public execution paths are exercised; isolated unit tests alone are not
  sufficient proof of integration.
- Migration, retry, recovery, and compatibility evidence is collected where
  the change affects those boundaries.
- The system can trace product direction to mission, task, implementation,
  evidence, and the resulting decision.

## Gate selection rule

Before evaluating work, record:

```text
gate type
subject and exact revision
decision authority
required evidence
outcome and reason
effect of allow, deny, or escalation
```

If the requested evidence cannot answer the stated governing question, the
evaluation is incomplete rather than implicitly broadened or narrowed.

## Anti-patterns

- Treating a polished handoff as proof of completed work.
- Treating a passing unit test as mission acceptance.
- Treating a worker's completion message as evidence or approval.
- Recording a required-invariant failure as a non-blocking residual risk.
- Letting a model choose both the task package and its binding readiness or
  acceptance outcome without deterministic, attributable governance.
