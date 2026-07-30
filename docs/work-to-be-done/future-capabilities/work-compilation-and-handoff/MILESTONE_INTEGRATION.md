# Milestone integration

| Milestone | Contribution of this capability |
| --- | --- |
| M1 | Provides durable records, revisions, provenance, authority, decisions, and audit links. No context compiler is added here. |
| M2 | Curates workspace sources, origin context, trust labels, and retrieval references. |
| M3 | Compiles mission-level context, decision registers, and ambiguity registers. |
| M4 | Compiles requirements, task graphs, test oracles, task-completion evidence expectations, and formal readiness assessments. |
| M5 | Compiles immutable, role-specific execution and handoff packets. |
| M6 | Checks semantic continuity from mission through evidence, task completion, and mission acceptance handoff. |
| M7 | Invalidates and recompiles affected packages after changed intent or review. |
| M8 | Measures package quality, ambiguity, drift, escalation, outcomes, and operational/release readiness to improve the compiler safely. |

## Productization sequence

1. Use the templates manually for M2–M4 planning.
2. Record repeated missing-context, ambiguity, and handoff failures.
3. Stabilize the record contracts that recur across real packages.
4. Implement deterministic readiness checks first.
5. Add model-assisted curation and cold-start evidence behind explicit,
   reviewable governance boundaries.

Do not implement a generic autonomous “context intelligence” feature before
the recurring contracts and failure modes have been observed in real work.
