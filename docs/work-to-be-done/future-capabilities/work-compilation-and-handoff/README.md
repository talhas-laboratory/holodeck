# Work compilation and handoff

**Status:** Proposed future capability; not current runtime behavior.

This package preserves the method used to turn Holodeck's broad product vision
and governance sources into the M1 implementation handoff. It is a design seed
for later context curation, task creation, agent handoff, and semantic
continuity work.

The central objective is:

> Compile the minimum sufficient, traceable work package for a particular role
> to perform a particular task without losing the direction from which that
> task was derived.

Context may be compacted for delivery, but its provenance and retrievability
must remain intact.

## Reading order

1. [Capability specification](CAPABILITY_SPEC.md)
2. [Abstraction and traceability model](ABSTRACTION_TRACEABILITY_MODEL.md)
3. [Handoff readiness rubric](HANDOFF_READINESS_RUBRIC.md)
4. [Gate taxonomy](GATE_TAXONOMY.md)
5. [Cold-start protocol](COLD_START_PROTOCOL.md)
6. [M1 case study](M1_CASE_STUDY.md)
7. [Milestone integration](MILESTONE_INTEGRATION.md)

The `templates/` directory supplies manual, reusable work-package templates.
They are not schemas or APIs yet.

## Relationship to existing sources

- `governance/05-context-compiler/` defines the run-specific deterministic
  context packet. This package adds the upstream work-compilation and readiness
  method that determines whether a task is ready to become such a packet.
- M3 owns mission and context compilation; M4 owns requirements, task graphs,
  tests, and readiness gates; M5 creates execution-specific packets; M6 checks
  semantic continuity, evidence, and completion handoffs; M8 owns operational
  and release readiness.
- M1 supplies durable records, authority, provenance, revisions, decisions,
  and auditability. This package does not change M1's scope.
