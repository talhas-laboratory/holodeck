# Worklog, evidence, and organizational learning

## Purpose

Capture what happened without demanding private chain-of-thought, then promote only validated learning into durable workspace knowledge.

## Three layers

1. Automatic trace: agent/tool metadata, commands, outputs, tests, files/diffs, permissions, errors, timing, and repository state.
2. Agent worklog: concise plans, assumptions, decisions, failures, strategy changes, uncertainty, recovery, handoff, and evidence links.
3. Durable knowledge: validated decisions, failure patterns, recovery procedures, invariants, and test strategies.

## Completion and interruption

A `CompletionCandidate` captures addressed requirements, claimed changes/tests, evidence, limitations, risks, rollback, continuation, and context gaps. The runtime mechanically checks it against trace/repository facts. Interrupted runs receive a recoverable evidence-based summary even without an agent final response.

## Promotion rules

Learning flows from observation to interpretation to supporting evidence to confirmation/approval to a versioned knowledge revision. Knowledge may be unverified, supported, verified, disputed, superseded, or archived. Redact secrets/personal data and preserve uncertainty rather than fabricated explanations.
