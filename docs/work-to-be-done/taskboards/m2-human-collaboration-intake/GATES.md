# Gates

## Intake

- The packet links the governing product and M1-handoff sources.
- It states authority ownership, scope, non-goals, external-state effects, and
  failure/replay behavior.

## Readiness

- Provider-neutral contracts and persistence boundaries precede provider code.
- All inbound and outbound idempotency keys, tenant checks, and correlation
  references are specified.
- The task names the M1 command/application seam it uses.

## Implementation

- Platform SDK and message-schema types remain outside domain modules.
- External messages are recorded as task origins, never silently treated as
  binding missions or approvals.
- Workspace selection is explainable; creation is proposed and reversible until
  its applicable human decision is recorded.

## Verification

- Tests include authentication/authorization, duplicate delivery, crash/retry,
  tenant isolation, rejection absence, and source-to-status correlation.
- Exact commands and results are recorded in the task packet.

## Done

- Acceptance criteria have direct evidence.
- Task packet, task index, lane, and updates agree.
- Residual risks and later-milestone deferrals are explicit.
