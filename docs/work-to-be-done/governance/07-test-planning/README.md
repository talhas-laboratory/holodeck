# Test planning and test generation

## Purpose

Generate verification from requirements, failure models, appropriate boundaries, and objective oracles rather than only from a worker's implementation.

## Required test plan

`TestPlan` includes requirement revisions, risk classification, failure hypotheses, layers, requirement coverage, test oracles, environment needs, holdouts, independence/human-evaluation conditions, pass policy, limitations, and approval status.

The failure model considers normal incorrectness, edge cases, partial failure, concurrency, stale state, retries, malformed inputs, authorization, crash recovery, and cross-component behavior. Every test has a correctness oracle, including forbidden outcomes and partial-state checks.

## Independence controls

Stage context: black-box requirements/interfaces first, architecture-risk context next, implementation internals last. Test agents can create/run isolated tests but cannot modify requirements, thresholds, failing tests, or worker code to satisfy their own tests. Protect holdouts from the worker.

## Acceptance

Each critical requirement maps to an oracle and suitable boundary. The system records whether evidence is worker-authored, independent, hidden, or runtime-derived; passing tests alone never satisfy a requirement without explicit coverage.
