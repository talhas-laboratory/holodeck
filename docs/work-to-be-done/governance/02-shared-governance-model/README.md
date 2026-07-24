# Shared governance model

## Purpose

Provide the stable identity, revision, provenance, trust, evidence, actor, role, and event conventions on which every later subsystem depends.

## Required behavior

- Persist immutable final records and explicit revisions for mutable concepts.
- Treat provenance as required reproducibility and disagreement-handling data, not optional metadata.
- Distinguish trust classes for context and knowledge, and evidence classes for acceptance.
- Model an actor as a human, agent instance, or service; model a role as a versioned operational contract with responsibilities, permissions, required outputs, reviewer rubric, blocking authority, and escalation conditions.
- Publish durable events without making event consumers part of the transactional write path.

## Acceptance

The runtime can identify who changed what, from which source and revision, under which role and trust status; reconstruct an object's history; and safely drive refresh, review, and audit consumers from idempotent events.

See [shared contracts](../shared/README.md).
