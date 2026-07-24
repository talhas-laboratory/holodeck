# Product decision guide

Agents must use this guide for product, architecture, integration, and
execution-model decisions.

## Start with the product outcome

Before choosing an implementation, answer:

1. How does this help a human initiate, supervise, or trust delegated work?
2. Which authority does the change belong to: collaboration, Holodeck
   governance, or repository/CI?
3. What is the smallest correct implementation that preserves a replaceable
   boundary?
4. What current capability is real, and what remains a proposal?

## Required invariants

A decision should preserve these invariants unless an explicit exception is
recorded:

- External messages are task origins, not binding mission definitions.
- External identities are mapped to explicit Holodeck actors and roles.
- Human approvals record the actor, signed source event, decision, object
  version, and timestamp.
- Duplicate external events cannot create duplicate Holodeck actions.
- Outbound collaboration updates survive retries and process crashes.
- A mission is immutable once a run begins.
- Runs are tied to a fixed repository revision and execution environment.
- Agent tools operate through explicit, enforceable permissions where
  available; advisory boundaries are labeled honestly.
- Workers cannot provide all evidence used to approve their own result.
- Chat status never silently replaces Holodeck task, run, evidence, or gate
  state.
- Platform-specific data remains in adapters or external-reference records.
- A collaboration integration can be replaced without rewriting domain logic.

## Preferred boundary tests

Reject or redesign an approach when:

- the kernel imports a platform-specific SDK into core domain logic;
- a channel ID becomes the only workspace identifier;
- a reaction is accepted without checking signer and target version;
- a model response directly performs a binding state transition;
- a worker is launched in a shared mutable directory without a deliberate
  environment decision;
- an event acknowledgement is treated as proof that downstream automation
  completed;
- the system cannot explain which source, actor, mission, revision, and
  evidence produced an acceptance decision;
- or a planned upstream feature is treated as a shipped dependency.

## Product vocabulary

Use these distinctions consistently:

- **Collaboration community:** tenant-visible human/agent communication space.
- **Holodeck workspace:** governed semantic model of a project or bounded work
  domain.
- **Execution workspace:** concrete checkout, worktree, sandbox, or environment
  created for a run.
- **Task origin:** the message, issue, incident, or request that initiated work.
- **Mission:** immutable compiled instructions, authority, requirements,
  context, environment expectations, and gates.
- **Run:** one attempt by assigned agents to execute a mission.
- **Evidence:** immutable, attributable support for a requirement or finding.
- **Acceptance:** a gate decision, never merely a worker status.

## Conflict and exception protocol

If the simplest local implementation conflicts with the product vision:

1. state the conflict explicitly;
2. determine whether it is an alpha limitation or a change in product
   direction;
3. keep the incompatible behavior behind a replaceable boundary where
   possible;
4. record the decision and migration seam; and
5. do not describe the temporary behavior as the intended end state.

## Final decision check

Before completing a material change, confirm:

- product alignment;
- authority ownership;
- adapter separability;
- identity and authorization;
- replay and failure behavior;
- workspace and revision isolation;
- evidence and acceptance implications;
- current-versus-planned capability labeling;
- and a credible verification path.
