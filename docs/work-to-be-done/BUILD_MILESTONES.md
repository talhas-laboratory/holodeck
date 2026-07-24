# Holodeck build milestones

**Status:** Active high-level roadmap  
**Purpose:** Turn the complete work-to-be-done library into a delivery sequence without replacing, compressing, or discarding its source material.

## How to use this roadmap

This is the planning entry point for future implementation work. Each milestone identifies the required outcome, governing source material, and proof of completion.

The source documents remain authoritative in their own areas:

- Product-vision documents define durable product direction and decision criteria.
- The governance library defines the operating model, records, controls, and lifecycle requirements.
- The architecture blueprint defines the modular product architecture and technical shape.
- Source code and tests establish current behavior.
- The Local Coordination Hardening board records a completed historical implementation tranche; it is not an open backlog.

When a milestone is selected, create a focused implementation board beneath `taskboards/` with scoped tasks, acceptance tests, decisions, and handoffs. Do not mark a milestone complete merely because code exists: its stated evidence and exit conditions must be demonstrably satisfied.

## Delivery principle

Holodeck is the governed execution kernel for agent work. A collaboration platform such as Buzz is an ingress and coordination surface, not a replacement for Holodeck's durable governance records, evidence model, policies, or acceptance decisions.

The earliest end-to-end vertical slice should prove this path:

```text
human message
  -> authenticated collaboration event
  -> durable origin and actor binding
  -> workspace selection or genesis
  -> bounded mission and controlled execution
  -> evidence, review, and acceptance decision
  -> status returned to the collaboration thread
```

Integrations must use a provider-neutral collaboration boundary.

## Current baseline — M0 complete

The historical Local Coordination Hardening taskboard is complete: **TASK-001 through TASK-012** are marked done. It established the initial local implementation and adoption surface, including claim behavior, migrations, lifecycle and HTTP correctness, container delivery, repository/package identity, API/MCP guidance, policy documentation, and local daemon support.

Those completed tasks are retained as evidence and constraints for later work. They are not represented as new build milestones below.

## M1 — Establish the durable governance kernel

**Detailed design and board:** [M1 durable governance kernel design](../plans/2026-07-24-m1-durable-governance-kernel-design.md) and [implementation taskboard](taskboards/m1-governance-kernel/README.md).

**Outcome:** Holodeck has one coherent, versioned record model for governed work. Every significant lifecycle transition is attributable, replayable, and enforceable by domain logic rather than convention.

**Build:**

- Define and persist the canonical work graph: workspace, source, actor, intent, mission, requirement, test, run, artifact, evidence, review, approval, escalation, and completion records.
- Make identity, provenance, ownership, lifecycle state, timestamps, policy version, and causal links explicit in the domain model.
- Establish append-only event and decision records, idempotent commands, stable identifiers, schema evolution, and migration discipline.
- Introduce a clear domain/service/storage/adapter separation so persistence, HTTP/CLI, and future agent/runtime adapters remain replaceable.
- Translate global invariants into executable validation and domain errors, including the rule that no high-impact transition can occur without required authority and evidence.

**Exit evidence:**

- A documented, versioned schema and event catalog with migration tests.
- Domain-level tests proving invalid state transitions, missing provenance, duplicate commands, and unauthorized approvals are rejected.
- A reconstructable work graph for a representative mission from origin through a terminal decision.

**Primary sources:** governance shared records and event catalog; sections 01, 02, and 06; appendices; architecture blueprint foundation, persistence, API, security, and implementation sections.

## M2 — Create governed workspaces from human collaboration

**Outcome:** A human can initiate work through a collaboration surface, and Holodeck can safely identify the actor, bind the source, select or create the appropriate workspace, and preserve the full origin context.

**Build:**

- Define a `CollaborationAdapter` contract for inbound messages, thread context, actor identity, attachments, outbound status, and event verification.
- Implement Buzz as the first adapter only after the generic contract exists; preserve original message, thread, sender, timestamps, and external IDs as durable source records.
- Build workspace intelligence and genesis: repository/project bindings, workspace discovery, eligibility checks, context acquisition, creation proposals, and explicit human decisions where needed.
- Record source trust, actor authorization, repository/project bindings, workspace purpose, and creation provenance before autonomous work begins.
- Return clear, durable status updates to the originating collaboration thread without making Buzz the system of record.

**Exit evidence:**

- A complete vertical slice can ingest an authenticated collaboration event and create a durable, queryable work origin.
- Workspace selection/genesis is explainable, policy-checked, and reversible before execution.
- The initiating human can see a correlated status update with a link or identifier for the governed work.

**Primary sources:** governance sections 03 and 04; architecture blueprint workspace/source/context/genesis and collaboration-facing modules; product vision and Buzz integration strategy.

## M3 — Compile context and intent into an accountable mission

**Outcome:** Unstructured human intent becomes a bounded, reviewable mission with explicit context, assumptions, delegation, authority, and stop conditions.

**Build:**

- Build deterministic context compilation from workspace records, repository/project bindings, source material, and approved references.
- Capture intent, interpretation, uncertainty, assumptions, scope, constraints, desired outcomes, and ambiguity resolution as first-class records.
- Create a mission compiler that produces an executable proposal rather than allowing agents to infer silent objectives at runtime.
- Define delegated roles, permitted actions, authority boundaries, escalation paths, budget/time bounds, and cancellation/stop conditions.
- Require human clarification or approval when confidence, authority, or material scope is insufficient.

**Exit evidence:**

- The same inputs produce an inspectable mission proposal with attributable sources and declared assumptions.
- A reviewer can determine what the system was asked to do, what it inferred, who authorized it, and why it may proceed.
- Ambiguous or over-broad requests are paused or escalated instead of silently becoming execution work.

**Primary sources:** governance sections 04 and 05; architecture blueprint intent, delegation, task, and mission-compilation modules.

## M4 — Define requirements, tests, and gates before execution

**Outcome:** A mission is not executable until success, safety, and evidence requirements have been compiled into verifiable requirements, tests, and policy gates.

**Build:**

- Produce requirement records that distinguish functional outcomes, non-functional constraints, safety/privacy expectations, acceptance criteria, and unresolved questions.
- Compile test strategies and test cases from the mission, including negative cases, regression risk, integration boundaries, and required evidence.
- Implement gate definitions and evaluation semantics for readiness, policy, approvals, quality, and release/acceptance decisions.
- Bind each gate to its authority, required inputs, evaluator, decision record, and effect on lifecycle progression.
- Keep policies advisory until enforcement is implemented and demonstrated; never represent a documented policy as an active control without proof.

**Exit evidence:**

- A mission cannot enter controlled execution without a complete requirement/test/gate package or a recorded authorized exception.
- Gate outcomes are durable, attributable, repeatable, and linked to the versioned policy and evidence used.
- Test failures and unmet requirements prevent downstream completion claims.

**Primary sources:** governance sections 06 and 07; architecture blueprint requirements, test compiler, gate, policy, and security sections.

## M5 — Run agents in controlled execution workspaces

**Outcome:** Approved missions can be executed by agents within bounded, observable environments that enforce applicable authority, resource, repository, and network constraints.

**Build:**

- Implement an environment compiler that turns an approved mission into an execution workspace with explicit repository, branch, credentials, tools, limits, and isolation settings.
- Add an agent-runtime boundary for launching, supervising, pausing, resuming, cancelling, and collecting results from agent work without embedding provider-specific logic in the governance core.
- Enforce capability, repository/project, branch, secret, network, filesystem, budget, timeout, and concurrency restrictions at the execution boundary.
- Record every agent run, material tool invocation, environment version, state change, and interruption/cancellation reason.
- Prefer existing workspace/runtime mechanisms supplied by an integration platform where they fit, while retaining Holodeck as the authority that approves the work and evaluates its evidence.

**Exit evidence:**

- An approved mission creates a controlled run with reproducible environment configuration and a complete lifecycle record.
- Unauthorized or out-of-scope execution is blocked by the runtime boundary, not merely described in guidance.
- A run can be stopped safely and leaves a durable explanation of what happened and what state remains.

**Primary sources:** governance section 09; architecture blueprint environment compiler, policy, execution, agent-adapter, and repository integration modules; product vision and Buzz integration strategy.

## M6 — Make evidence, traceability, and completion decisions real

**Outcome:** Holodeck can prove what was done, connect it to requirements and tests, and make a defensible completion or acceptance decision rather than treating agent output as self-validating.

**Build:**

- Build the worklog, trace, artifact, evidence, and completion graph linking origin, mission, requirements, tests, gates, runs, outputs, reviews, and decisions.
- Define evidence collection, integrity metadata, retention, access control, and reproducibility expectations for code, test results, logs, artifacts, and human decisions.
- Implement completion and acceptance evaluators that distinguish “run ended,” “work produced,” “requirements satisfied,” and “accepted by the required authority.”
- Publish concise status and evidence summaries through collaboration adapters while retaining the full audit trail in Holodeck.
- Add semantic-handoff checks so human-readable outputs accurately represent the governed record rather than an agent's unsupported narrative.

**Exit evidence:**

- For a completed mission, a reviewer can traverse from the human request to every material outcome and see the evidence supporting each acceptance claim.
- The system refuses a completion claim when required tests, gates, evidence, or authority are absent.
- An external collaboration update can be reconciled to its internal decision and evidence identifiers.

**Primary sources:** governance section 08; architecture blueprint traceability, evidence, semantic handoff, gate, and lifecycle modules.

## M7 — Add review, revision, escalation, and human control

**Outcome:** Holodeck handles disagreement, defects, changed intent, and elevated-risk work through structured review and revision loops instead of informal, lossy conversation.

**Build:**

- Implement review assignments, findings, severity, dispositions, revision requests, rework missions, and approval/rejection decisions.
- Make escalation rules explicit for uncertainty, policy conflicts, security/privacy risk, cost/time overruns, authority gaps, and unresolved review findings.
- Preserve decision rationale, reviewer identity, policy version, superseded artifacts, and causal links across revision cycles.
- Support human intervention from collaboration surfaces without allowing a message alone to bypass authorization, gate, or evidence requirements.
- Ensure a revised mission invalidates or re-evaluates affected requirements, tests, gates, and evidence rather than inheriting completion by accident.

**Exit evidence:**

- A reviewer can reject or request revision of work and the system creates a traceable, bounded follow-up path.
- Escalations reach the correct human authority with enough context to decide safely.
- Superseded and accepted states are distinguishable in the work graph and external status view.

**Primary sources:** governance section 10; architecture blueprint review, findings, revision, decision, and collaboration-facing modules.

## M8 — Verify the whole lifecycle, learn, and operate it reliably

**Outcome:** Holodeck is demonstrably reliable as a governed execution system across lifecycle boundaries, and can improve using measured outcomes without weakening its controls.

**Build:**

- Implement independent verification across the end-to-end lifecycle, including integration, adversarial, failure/recovery, authorization, policy, evidence, and replay scenarios.
- Add learning records and controlled feedback loops from outcomes, reviews, defects, overrides, and recurring escalations; changes to policy or behavior remain versioned and governed.
- Establish operational readiness: observability, audit/query tooling, incident handling, backup/recovery, data retention, performance/capacity targets, and deployment/runbook standards.
- Measure product and governance health: trace completeness, gate effectiveness, review/revision rates, human intervention, mission success, cost/time, reliability, and unsafe/unsupported claim rates.
- Expand adapters, infrastructure, and scale only after the governed vertical slice is proven; do not trade auditability or authority controls for integration speed.

**Exit evidence:**

- A realistic end-to-end mission passes independent acceptance tests covering ingress, workspace genesis, mission compilation, execution, evidence, review, completion, and outbound status.
- Failure, interruption, and recovery tests show no unsupported completion, lost authority, or unreconciled material state.
- Operational documentation and telemetry allow an operator to explain and recover the system's current state.

**Primary sources:** governance sections 11, 12, and 13; architecture blueprint integration, operational, maintenance, readiness, metrics, roadmap, and anti-pattern sections.

## Scope and dependency map

| Milestone | Depends on | Establishes for later work |
| --- | --- | --- |
| M1 — Governance kernel | M0 baseline | trusted records, state, provenance, policy, and events |
| M2 — Collaboration and workspace genesis | M1 | governed human ingress and durable workspace context |
| M3 — Context and mission compilation | M1, M2 | bounded, authorized work proposals |
| M4 — Requirements, tests, and gates | M1, M3 | executable readiness and acceptance criteria |
| M5 — Controlled execution | M1, M4 | bounded agent runs and environment evidence |
| M6 — Evidence and completion | M1, M4, M5 | defensible completion and collaboration status |
| M7 — Review and revision | M3–M6 | controlled rework and human intervention |
| M8 — Independent verification and operations | M1–M7 | reliable, measurable, scalable system operation |

M2 through M6 should be planned as one thin vertical slice before broadening the system: a real human request should travel all the way to a governed decision and back to the originating conversation.

## Complete source-coverage map

This map confirms where every folder in `docs/work-to-be-done/` is represented. A source may guide more than one milestone; no source is retired by this roadmap.

| Source folder or document | Included through | Role in the roadmap |
| --- | --- | --- |
| [`README.md`](README.md) | M0–M8 | Navigation and authority boundaries for the work-to-be-done library. |
| [`governance/00-source/`](governance/00-source/) — original DOCX, front matter, and source notes | M1–M8 | Canonical visual/narrative governance source. Its 13 chapters and appendices are decomposed below; retain it for full wording and diagrams. |
| [`governance/shared/`](governance/shared/) | M1 | Global invariants, canonical records, and event vocabulary that underpin every later milestone. |
| [`governance/01-executive-design/`](governance/01-executive-design/) | M1 | System purpose, design principles, and governance operating model. |
| [`governance/02-shared-governance-model/`](governance/02-shared-governance-model/) | M1 | Identity, revisions, provenance, trust, evidence, actors, roles, and event conventions. |
| [`governance/03-workspace-intelligence/`](governance/03-workspace-intelligence/) | M2 | Workspace discovery, selection, source binding, and intelligence. |
| [`governance/04-curation/`](governance/04-curation/) | M2, M3 | Structured workspace and task curation, creation authority, inputs, and handoff into mission formation. |
| [`governance/05-context-compiler/`](governance/05-context-compiler/) | M3 | Context assembly, interpretation, assumptions, and bounded mission inputs. |
| [`governance/06-work-graph-requirements-gates/`](governance/06-work-graph-requirements-gates/) | M1, M4 | Task meaning, requirements, lifecycle gates, traceability, and authorization semantics. |
| [`governance/07-test-planning/`](governance/07-test-planning/) | M4 | Failure models, test planning, validation, and acceptance evidence requirements. |
| [`governance/08-work-evidence-learning/`](governance/08-work-evidence-learning/) | M6, M8 | Traces, worklogs, evidence, completion, recovery, and lifecycle learning signals. |
| [`governance/09-agent-adapters-enforcement/`](governance/09-agent-adapters-enforcement/) | M5 | Controlled execution, completion protocol, enforcement, and runtime accountability. |
| [`governance/10-review-loop/`](governance/10-review-loop/) | M7 | Revision-based reviews, findings, escalations, and decisions. |
| [`governance/11-integrated-lifecycle/`](governance/11-integrated-lifecycle/) | M2–M8 | Complete governed lifecycle and failure paths, verified throughout the vertical slice. |
| [`governance/12-roadmap/`](governance/12-roadmap/) | M1–M8 | Original A–H governance sequencing; translated into the milestones above without removing its detail. |
| [`governance/13-system-acceptance/`](governance/13-system-acceptance/) | M8 | Whole-system readiness and final acceptance criteria. |
| [`governance/appendices/`](governance/appendices/) | M1–M8 | Supporting schemas, catalogs, definitions, and cross-cutting reference material. |
| [`governance/README.md`](governance/README.md) and each governance section README | M1–M8 | Library index and concise entry points; detailed specifications remain in the corresponding folders. |
| [`product-architecture-blueprint/`](product-architecture-blueprint/) | M1–M8 | Technical architecture: foundation/persistence/API (M1); workspace/source/context/genesis (M2); intent/task/mission compiler (M3); requirements/test/gates (M4); environment/execution/adapters (M5); trace/evidence/semantic handoff (M6); review/revision (M7); integration, operations, maintenance, metrics, roadmap, and anti-patterns (M8). |
| [`taskboards/local-coordination-hardening/`](taskboards/local-coordination-hardening/) | M0 and all later work | Completed TASK-001–TASK-012, board, gates, decisions, task packets, and updates. Preserved as historical evidence, baseline constraints, and a template for future scoped taskboards. |

## Guardrails for future boards

- Do not create a separate “Buzz product” inside Holodeck. Implement an adapter boundary and keep Holodeck's governance model authoritative.
- Do not treat inbound messages, agent claims, or generated summaries as approvals or evidence without durable actor binding, authorization, and required evaluation.
- Do not expose a policy as enforced until the actual runtime, command, or gate rejects violations and tests prove it.
- Do not expand into broad multi-agent orchestration, cloud-scale infrastructure, or many integrations before the M2–M6 governed vertical slice works end to end.
- Do not replace source documents with this roadmap. Link implementation tasks back to the relevant governance and blueprint sections so their details remain available at the point of work.
