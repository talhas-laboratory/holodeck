# Buzz integration strategy

## Assessment record

- Researched: 2026-07-23
- Buzz repository: <https://github.com/block/buzz>
- Inspected Buzz commit:
  [`06e3d82b04ab326a36694264ffb4b9dd94ec5661`](https://github.com/block/buzz/commit/06e3d82b04ab326a36694264ffb4b9dd94ec5661)
- Assessment: strong strategic alignment, viable adapter integration, incomplete
  end-to-end autonomous execution support in Buzz today.

Claims about current Buzz behavior in this document must be revalidated before
implementation because the upstream project is evolving rapidly.

## Conclusion

Holodeck and Buzz are complementary.

- Buzz is the human-and-agent collaboration surface, identity system, signed
  event log, channel model, and Git/workflow substrate.
- Holodeck is the governed mission, workspace, execution, evidence, and
  acceptance kernel.

Buzz's architecture permits Holodeck to integrate as an external service over
Nostr WebSocket/HTTP, ACP, MCP, and Git events. Holodeck should not be embedded
into the Buzz relay and should not make Buzz chat the authority for mission
state.

## Concept mapping

| Buzz | Holodeck |
|---|---|
| Community selected by relay host | Tenant or organization boundary |
| Project or repository | Semantic workspace |
| Project/repository channel | Workspace collaboration surface |
| Human message or forum post | Task origin |
| Thread | Task supervision context |
| Branch channel | Mission/run collaboration room |
| Human or agent npub | External actor identity |
| Agent turn | Run activity |
| Reaction or approval event | Candidate gate decision |
| NIP-34 patch or ref event | Artifact or repository evidence |
| Workflow | External trigger and notification mechanism |

The important distinction is that a Buzz community is broader than a Holodeck
workspace. A Buzz community may contain multiple projects and repositories.
Initial integrations should use explicit bindings until Buzz project binding is
fully implemented.

## Verified Buzz capabilities

Buzz currently provides:

- a self-hosted relay that is authoritative for Buzz event state;
- signed Nostr events with stable event IDs;
- NIP-42 WebSocket and NIP-98 HTTP authentication;
- host-derived community isolation and channel membership checks;
- channels, threads, forums, DMs, search, media, and audit facilities;
- durable event persistence and WebSocket subscriptions;
- an agent-oriented JSON CLI;
- an ACP harness that turns mentions into agent prompts;
- support for ACP agents including Goose, Codex, Claude Code, and Buzz's own
  agent;
- MCP injection into agent sessions;
- message, reaction, schedule, and webhook workflow triggers;
- Git Smart HTTP hosting and NIP-34 Git events.

Primary upstream references:

- [Buzz architecture](https://github.com/block/buzz/blob/main/ARCHITECTURE.md)
- [Buzz ACP harness](https://github.com/block/buzz/blob/main/crates/buzz-acp/README.md)
- [Buzz agent architecture](https://github.com/block/buzz/blob/main/VISION_AGENT.md)
- [Buzz project vision and status](https://github.com/block/buzz/blob/main/VISION_PROJECTS.md)
- [Buzz capability maturity table](https://github.com/block/buzz#works-today--being-wired-up--strong-opinions-pending-code)

## Important Buzz limitations

### Job kinds are not a complete job runtime

Buzz defines kinds `43001` through `43006` for job request, acceptance,
progress, result, cancellation, and error. In the inspected commit, these kinds
are registered and surfaced in activity data, but no complete executor was
found that turns a job request into an isolated coding workspace and governed
run.

Holodeck may publish or consume these event kinds once their schema and
semantics are stable, but it must initially own job execution.

### ACP sessions do not provision task workspaces

`buzz-acp` supplies its process working directory to ACP sessions. Desktop
managed agents normally start from a persistent Buzz home. It does not
currently create a repository-bound worktree or disposable environment for
each task.

Holodeck must supply the Workspace Provisioner and pass the resulting directory
and environment into its ACP launcher.

### Workflow approvals are incomplete

Buzz contains approval kinds, persistence structures, grant/deny handlers, and
resume-oriented code. The current workflow engine nevertheless marks a run
failed when it reaches `request_approval`, before it creates a resumable waiting
state.

Holodeck should own mission and acceptance gates. A signed Buzz event may be
evidence of a human decision, but Holodeck must validate the actor, target,
object version, and authorization before applying it.

### Buzz is not an execution sandbox

Buzz bounds process lifetime and output in its developer tooling, but its shell
runs with the operator's trust. Holodeck still requires controlled filesystem,
network, secrets, resource, and repository policies before claiming execution
authority.

### Workflow side effects are not transactional completion

Buzz persists the originating event before asynchronously starting search,
audit, and workflow side effects. Event acceptance proves event ingestion, not
successful downstream automation. Holodeck needs its own receipts, retries, and
observable processing state.

## Recommended architecture

```text
Buzz clients
  human message / reaction / Git event
                    |
                    v
                Buzz relay
                    |
          signed event subscription
                    |
                    v
           Holodeck Buzz adapter
       actor mapping / receipts / outbox
                    |
                    v
             Holodeck kernel
     workspace / mission / claims / gates
             /                 \
            v                   v
 workspace provisioner      ACP launcher
 worktree + environment     worker/reviewer/verifier
            \                   /
             v                 v
             repository and CI
                    |
          evidence and gate decision
                    |
                    v
       originating Buzz thread/channel
```

## Authority partition

### Buzz owns

- external human and agent identities;
- community and channel membership;
- signed conversation and reaction events;
- threads, notifications, presence, and search;
- Buzz-hosted Git transport and NIP-34 metadata.

### Holodeck owns

- actor-role mappings used for Holodeck authorization;
- workspace semantics and readiness;
- task interpretation and delegation contracts;
- immutable missions and requirements;
- runs, claims, permissions, and execution state;
- evidence coverage, findings, and gate decisions;
- acceptance and semantic handoff.

### Repository and CI own

- commit and tree identity;
- code and built artifacts;
- executable test results;
- branch protection and merge enforcement.

Every cross-boundary record must preserve stable external references.

## Proposed interaction

1. A human sends an explicit intake command such as `@holodeck work: ...`.
2. The Buzz adapter receives the signed event and records an idempotent receipt.
3. It validates the community, channel, signer, role, and supported command.
4. It resolves an explicit project/repository binding to a Holodeck workspace,
   or starts workspace genesis when permitted.
5. It records the Buzz event as the task origin.
6. The Holodeck curator proposes the intent interpretation, delegation
   contract, requirements, risk, and missing clarification.
7. Holodeck requests human approval when the risk or ambiguity policy requires
   it.
8. A signed, authorized Buzz decision satisfies the applicable definition
   gate.
9. Holodeck compiles an immutable mission tied to a repository revision.
10. The Workspace Provisioner creates an isolated execution workspace.
11. The ACP launcher assigns worker, reviewer, and verifier roles with
    role-specific MCP tools and context.
12. Holodeck publishes concise progress, blockers, decisions, and findings into
    the originating Buzz thread through a durable outbox.
13. Workers submit requirement-linked evidence; independent verification and
    policy checks run.
14. Holodeck records the acceptance decision and publishes the exact revision,
    evidence summary, limitations, and outcome back to Buzz.

Ordinary messages must not become executable tasks automatically. The intake
syntax, permitted channels, authorized actors, and automation level must be
explicit.

## Required Holodeck additions

### Collaboration boundary

Introduce a provider-neutral adapter interface capable of:

- receiving and checkpointing external events;
- resolving external actors and collaboration locations;
- publishing threaded messages and status;
- requesting and receiving signed decisions;
- linking external artifacts and repository events.

`BuzzAdapter` should implement this interface without placing Buzz types inside
the kernel.

### Persistence

Add relational records for:

- collaboration endpoints and bindings;
- external actor bindings;
- external event receipts;
- task origins and external references;
- transactional outbound messages;
- workspace-to-repository bindings;
- actor-attributed approvals and gate decisions.

Receipts require a uniqueness constraint on provider plus external event ID.
Outbound messages require stable idempotency keys.

### Workspace provisioning

Introduce a replaceable `WorkspaceProvisioner` responsible for:

- resolving the repository;
- fixing the base revision;
- creating or recovering an isolated worktree or sandbox;
- applying filesystem, network, secrets, and resource policy;
- recording environment identity;
- cleanup and interrupted-run recovery.

### Agent launching

Introduce an ACP-first `AgentLauncher`. It should:

- launch any compatible agent in the provisioned execution workspace;
- inject the Holodeck MCP server and role-specific tools;
- bind the process to the Holodeck run and external actor identity;
- capture structured activity and cancellation;
- support separate worker, reviewer, and verifier roles;
- avoid relying on a shared chat channel as its queue or state store.

### Governance hardening

Before Buzz decisions become authoritative, Holodeck must:

- record the approving actor and signed source event;
- bind approval to the exact proposal, mission, or gate version;
- replace free-form evidence references with immutable artifact identity,
  producer, verifier, command, status, and provenance;
- expose governed mission operations through MCP;
- keep policy labeled advisory until controlled adapters enforce it.

## Phased path

### Phase 1 — Reliable message-to-task bridge

- collaboration adapter boundary;
- Buzz community/channel/repository bindings;
- actor mappings;
- external event receipts and outbound outbox;
- explicit `@holodeck work` intake;
- task creation and threaded status;
- actor-attributed approvals.

This phase proves reliable ingress and supervision without launching workers.

### Phase 2 — Governed execution workspace

- repository binding and fixed revision;
- worktree-based Workspace Provisioner;
- ACP AgentLauncher;
- Holodeck MCP mission tools;
- run recovery, claims, and cancellation;
- progress publication into the source thread.

### Phase 3 — Evidence and acceptance

- structured completion candidates;
- immutable evidence records;
- independent reviewer and verifier roles;
- signed gate decisions;
- CI and branch-protection backstops;
- semantic final handoff.

### Phase 4 — Protocol and scale

- compatible use of stable Buzz job events;
- project/branch binding as upstream Buzz support matures;
- multi-community tenancy;
- scalable persistence behind existing storage boundaries;
- optional hosted execution providers.

## Decision

Build Holodeck so Buzz can be its first rich collaboration adapter, not its
parent platform.

The initial integration should be external and protocol-based. Holodeck should
reuse Buzz identity, conversation, ACP/MCP, and Git surfaces while retaining
deterministic ownership of workspace, mission, execution, evidence, and
acceptance state.
