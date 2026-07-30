# Shared contracts

These are the contracts used by multiple proposals. They must be established before subsystem-specific behavior so that authority, versioning, provenance, and lifecycle semantics remain consistent.

## Global invariants

- Every durable object has a globally unique opaque ID.
- Mutable conceptual objects expose explicit revisions. Finalized runs, packets, candidate revisions, reviews, evidence artifacts, and acceptance decisions are immutable.
- Corrections create a new revision linked to the superseded record.
- Changes include UTC timestamp, actor, source, provenance, trust class, and schema version where applicable.
- Facts, claims, and validated knowledge are distinct. Observed trace data is fact within its instrumentation boundary; agent explanations are claims; only validated and versioned knowledge is authoritative.
- Events are append-only, idempotently consumable, and emitted after persistence. They include event type, actor, timestamp, subject IDs, causation ID, correlation ID, and payload schema version.

## Canonical object inventory

`WorkspaceModel`, `WorkspaceSource`, `ContextModule`, `RoleProfile`, `TaskPosition`, `Requirement`, `TestPlan`, `ContextPacket`, `ContextExpansionRequest`, `RunTraceEvent`, `WorklogEvent`, `CompletionCandidate`, `CandidateRevision`, `ReviewRequest`, `Review`, `Finding`, `FindingResponse`, `VerificationEvidence`, `AcceptanceDecision`, `KnowledgeCandidate`, and `KnowledgeRevision`.

## Event catalogue

`workspace.intelligence.onboarding_requested`, `workspace.model.proposed`, `workspace.model.approved`, `workspace.context_module.stale`, `workspace.knowledge_gap.created`, `task.curation.requested`, `task.position.created`, `requirement.proposed`, `requirement.approved`, `gate.evaluation.completed`, `context.packet.compiled`, `context.expansion.requested`, `run.started`, `run.trace_event.recorded`, `run.worklog_event.recorded`, `run.interrupted`, `completion_candidate.submitted`, `candidate_revision.created`, `review.requested`, `review.finding.created`, `review.finding.responded`, `review.finding.resolved`, `review.finding.escalated`, `verification.started`, `verification.evidence.recorded`, `acceptance.decision.created`, `knowledge_candidate.created`, `knowledge.promoted`, and `knowledge.superseded`.
