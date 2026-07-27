# Capability specification

## Product outcome

Help a human safely delegate work by ensuring an assigned agent receives a
bounded, role-appropriate package that preserves the relevant intent,
authority, constraints, decisions, and proof obligations.

The capability does not replace human judgment, governance decisions, Git/CI,
or collaboration platforms. It compiles durable Holodeck records and approved
sources into inspectable work packages.

## Proposed flow

```text
trusted sources and workspace state
→ context curation
→ mission context bundle
→ requirements and task graph
→ task-specific handoff packet
→ readiness evaluation
→ role-specific execution packet
→ task evidence and completion evaluation
→ milestone/release certification as applicable
```

## Proposed components

| Component | Responsibility | Authority boundary |
| --- | --- | --- |
| Context curator | Select, classify, and explain relevant source material. | May propose selections; cannot promote trust or authorize work. |
| Context compiler | Produce a versioned mission-level bundle. | Deterministically applies precedence, provenance, and omission rules. |
| Work decomposer | Propose requirements, tasks, and dependency relationships. | Proposes only; governed commands create binding records. |
| Handoff compiler | Produce a task- and role-specific package. | Cannot alter mission, authority, or requirements. |
| Readiness evaluator | Check structural completeness and required governance conditions. | Deterministically permits, denies, or escalates assignment. |
| Cold-start verifier | Tests whether an independent agent understands a package. | Supplies evidence to readiness; never authorizes alone. |
| Continuity evaluator | Compares mission, task, outcome, and handoff claims. | Supplies evidence to later review/acceptance gates. |
| Gate coordinator | Selects the appropriate gate for the question being asked. | Cannot treat readiness evidence as completion or acceptance evidence. |

## Design principles

- Preserve a path from task to mission, workspace purpose, and product
  direction.
- Keep source facts, generated interpretations, and binding instructions
  distinct.
- Give each role the minimum sufficient context, not the entire corpus.
- Record omitted material, selection reasons, trust labels, and retrieval paths.
- Make task readiness risk-adjusted: exploratory work can retain bounded
  unknowns; implementation work needs explicit contracts and test oracles.
- Treat model output as a proposal or evaluation input. Binding task creation,
  authority, and readiness remain kernel-controlled.
- A gate answers one explicit question. Readiness to start, completion of a
  task, acceptance of a mission, and operational release readiness are not
  interchangeable claims.

## Explicit non-goals

- A universal prompt generator.
- A free-form policy language.
- A replacement for the deterministic context-packet contract in governance
  section 05.
- Automatic approval of a task because a model says it is ready.
- Copying complete source corpora into every agent context.
