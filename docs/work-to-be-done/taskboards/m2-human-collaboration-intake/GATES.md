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
- Repository graph work names the exact repository revision, source
  observations, extractor identity/version/configuration, resource limits, and
  coverage behavior.
- Provider licensing and redistribution are resolved before a dependency is
  accepted into production scope.

## Implementation

- Platform SDK and message-schema types remain outside domain modules.
- External messages are recorded as task origins, never silently treated as
  binding missions or approvals.
- Workspace selection is explainable; creation is proposed and reversible until
  its applicable human decision is recorded.
- Repository facts are immutable, evidence-backed, and revision-scoped.
- Partial or failed extraction cannot replace the active factual snapshot.
- Extractor-native schemas, databases, and IDs do not become Holodeck's
  canonical domain model.
- Interpretive claims and risk clearance remain outside the M2 factual graph.

## Verification

- Tests include authentication/authorization, duplicate delivery, crash/retry,
  tenant isolation, rejection absence, and source-to-status correlation.
- Graph tests additionally include golden fact accuracy, deterministic
  extraction, revision mismatch, full/incremental equivalence, bounded
  traversal, partial coverage, historical reconstruction, and concurrent
  activation.
- Exact commands and results are recorded in the task packet.

## Done

- Acceptance criteria have direct evidence.
- Task packet, task index, lane, and updates agree.
- Residual risks and later-milestone deferrals are explicit.
