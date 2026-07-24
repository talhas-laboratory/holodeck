# Product vision

## North star

Holodeck is the governed execution space in which agents organize and complete
bounded work initiated by humans.

A human should be able to send an initial message from a collaboration platform
and remain in that platform while Holodeck:

1. identifies the human, project, conversation, and authority context;
2. finds or creates the relevant semantic workspace;
3. separates the literal request from desired outcome, constraints, non-goals,
   risk, and delegated authority;
4. compiles an inspectable, versioned mission;
5. provisions a repository-bound and appropriately isolated execution
   workspace;
6. assigns and coordinates workers, reviewers, and verifiers;
7. reports meaningful progress into the originating conversation;
8. collects requirement-linked evidence; and
9. accepts work only through the applicable gates.

The human-facing platform is where collaboration happens. Holodeck is where
delegated work becomes governed and executable.

## Product thesis

Agent autonomy becomes useful when it is easy to initiate and safe to trust.

Chat alone provides convenient delegation but weak authority, scope,
reproducibility, and acceptance. A task database alone provides records but not
the collaborative surface where humans naturally supervise work. Holodeck joins
the two without trying to replace either:

- human intent enters through a familiar collaboration surface;
- model-based agents contribute judgment and implementation;
- a deterministic kernel controls authority, state, permissions, claims,
  versioning, and gates;
- isolated workspaces make execution reproducible and conflict-aware;
- evidence and independent verification determine completion; and
- the originating conversation remains the visible supervision surface.

## Product boundary

Holodeck should own:

- semantic workspace genesis and readiness;
- sources, provenance, trust classes, and uncertainty;
- intent kernels and delegation contracts;
- mission, requirement, context, environment, and test-plan compilation;
- task and run state machines;
- agent roles, delegation, claims, and conflict control;
- controlled workspace and tool access;
- work traces, evidence, findings, and gate decisions;
- final semantic handoff and acceptance.

Holodeck should integrate with, rather than own:

- chat, channels, threads, reactions, and notifications;
- external human and agent identity systems;
- social presence and community membership;
- general-purpose Git hosting;
- general-purpose artifact storage;
- model providers and agent implementations;
- CI platforms and deployment systems.

## Enduring architectural principles

### The kernel has authority

Agents may interpret, propose, plan, implement, test, and review. Deterministic
services must control binding state transitions, permissions, claims, version
selection, approval rules, evidence requirements, and acceptance.

### Collaboration platforms are adapters

Buzz, Slack, Teams, a CLI, or a future interface should enter through a
provider-neutral collaboration boundary. Holodeck's domain model must not
depend on one platform's message schema, identity type, or workflow engine.

### Workspaces are semantic and executable

A Holodeck workspace is not merely a chat community or directory. It combines
project purpose, authority, sources, policies, repository bindings, readiness,
and execution constraints. A run receives a concrete environment derived from
that workspace and a fixed mission.

### Conversation is not coordination authority

Messages are valuable intent and supervision events, but chat history must not
be the only record of task state, claims, delegation, evidence, or approval.
Those records belong in Holodeck and reference their originating external
events.

### Completion is evidence-based

A worker submits a completion candidate. Requirements, test results,
independent findings, policy checks, and applicable human approvals determine
whether the mission is accepted.

### Authority remains partitioned

There is no single universal source of truth:

- the collaboration platform is authoritative for signed conversation and
  membership events;
- Holodeck is authoritative for mission and execution-governance state;
- Git and CI are authoritative for revisions, artifacts, and executable
  verification.

Objects crossing a boundary carry stable references in both directions.

### Integration must be replay-safe

External event ingestion must be authenticated, idempotent, checkpointed, and
recoverable. Outbound updates must use a durable outbox. A reconnect, duplicate
delivery, or process crash must not create duplicate tasks or lose final status.

### Autonomy is risk-adjusted

Low-risk, reversible, well-specified work may proceed automatically. Ambiguous,
irreversible, security-sensitive, or high-impact work requires clarification,
reduced permissions, additional verification, or explicit approval.

## Intended product experience

The desired interaction is:

> A human addresses Holodeck in a project conversation. Holodeck acknowledges
> the request, shows its interpretation and any material unknowns, creates or
> selects the correct workspace, and proposes a bounded mission. Once the
> applicable gate is satisfied, it provisions the work environment and
> coordinates agents. The conversation shows concise progress, decisions,
> blockers, findings, and evidence. The final response links the exact
> revision, tests, unresolved uncertainty, and acceptance decision.

Agents should feel like first-class collaborators to the human, but their
authority must remain explicit, inspectable, and bounded.

## Non-goals

Holodeck should not become:

- another chat platform;
- a replacement for Git or CI;
- a single opaque agent that interprets, implements, and approves its own work;
- a prompt-only coordination convention;
- a platform-specific Buzz extension;
- a claim of sandboxing when only advisory policy exists;
- a system that interprets every ordinary message as executable work;
- or a dark software factory for work whose intent and verification are not
  sufficiently defined.
