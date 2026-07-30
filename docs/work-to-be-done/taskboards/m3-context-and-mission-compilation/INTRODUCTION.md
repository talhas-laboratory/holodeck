# M3 introduction — from a request to an accountable proposal

M3 is the point at which Holodeck turns a durable request into an explicit,
inspectable proposal for governed work. It is not an agent launcher, a generic
repository search feature, or a system for turning a chat message directly
into execution.

Its purpose is to answer, before implementation begins:

> What was requested, what does it mean in this workspace and repository
> revision, what is known versus inferred, what is allowed, what remains
> uncertain, and what exact context should each role receive?

The result is a bounded mission proposal plus compact, immutable,
role-specific context packets. A human or a later milestone can inspect those
objects instead of relying on an agent's private reasoning or an evolving chat
thread.

## Why M3 exists

An external message is valuable evidence of intent, but it is not itself an
execution contract. It can be ambiguous, omit constraints, refer to an old
repository state, or ask for work beyond the sender's authority. Likewise, a
repository graph can reveal evidence-backed structure, but it cannot establish
runtime truth, product intent, or permission to act.

M3 makes those boundaries visible. It preserves literal human input, combines
it with approved workspace knowledge and a fixed repository snapshot, and
labels every task-local interpretation as an inference rather than a fact. When
the evidence, authority, or scope is insufficient, M3 lowers readiness or
requests clarification; it must not silently broaden the task.

This supports the product's central promise: agents may propose and reason,
while deterministic Holodeck services retain control of authority, versioning,
and binding state transitions.

## Place in the delivery flow

```text
M2: authenticated origin + workspace model + factual graph snapshot
                                  |
                                  v
M3: typed task + task position + bounded context + mission proposal
                                  |
                                  v
M4: requirements + test strategy + gates
                                  |
                                  v
M5: fixed execution environment + controlled agent run
                                  |
                                  v
M6: evidence review + acceptance decision
```

M2 owns the source facts that M3 consumes: task origins and source manifests,
approved workspace intelligence, and immutable, revision-scoped repository
graph snapshots. M3 must preserve M2's provenance, trust, freshness, coverage,
and omission semantics. It does not change M2 facts or promote its own model
output into the factual graph.

M4 decides what must be true and how it will be tested. M5 creates the
execution workspace and launches bounded workers. M6 evaluates evidence and
acceptance. M3 supplies those later stages with a transparent starting
contract; it does not pre-empt their authority.

## Inputs, processing, and outputs

| Stage | M3 does | It preserves |
| --- | --- | --- |
| Typed intake | Classifies the task and determines `READY`, `DISCOVERY_READY`, or `BLOCKED`. | Literal request, source references, observed versus inferred fields. |
| Task position | Records outcome, scope, non-goals, constraints, assumptions, authority, risk, confidence, ambiguity, and decisions as immutable revisions. | Conflicting interpretations and material unknowns. |
| Factual context plan | Resolves candidate code entities and uses M2's bounded queries under explicit depth, result, and traversal budgets. | Graph paths, source revisions, coverage gaps, empty results, truncation, and omissions. |
| Optional probes | Tests narrowly defined task-local hypotheses about data/state/contracts or authority/security/control. | Premises, alternatives, limitations, invalidation conditions, and verification obligations. |
| Context selection | Selects the smallest sufficient material for a given role under authority, freshness, relevance, and token budgets. | Trust layer, selection reason, exclusion reason, retrieval handle, and residual risk. |
| Packet compilation | Produces a canonical, content-hashed, immutable role-specific context packet. | Exact inputs, compiler configuration, omitted material, and provenance index. |
| Mission proposal | States allowed work, boundaries, roles, budgets, stop conditions, escalation, expected outputs, and blockers. | The durable source of every proposed field and the limits on authority. |

The mission proposal and packet are deliberately different objects. The packet
is the reproducible context supplied to a role; the proposal is the inspectable
statement of intended, bounded work. Neither object can grant its own authority
or start a run.

## Evidence, trust, and authority model

M3 has four distinct kinds of material. They must never collapse into one
undifferentiated prompt:

1. Literal human input and approved decisions: records of what a person said
   or authorized.
2. Approved workspace knowledge and role contracts: versioned binding
   instructions within their proper jurisdiction.
3. M2 factual repository evidence: revision-scoped observations with source
   provenance and explicit coverage limits.
4. Generated interpretations, summaries, and harness plans: attributable,
   task-local proposals that are not instruction authority or repository fact.

Context precedence is fixed: platform governance, approved workspace
instructions, role contract, human task/approved requirements, run-specific
permissions, authoritative references, untrusted/generated references, then
history and summaries. A lower-trust source can inform a role but cannot
override an instruction layer.

The same discipline applies to uncertainty. An interpretive probe can be
`activated`, `cleared`, `unresolved`, or `conflicted`. A clearance needs an
explicit bounded evidence argument; an empty search result or absent graph edge
is `unresolved`, not proof of safety or non-impact.

## Minimum sufficient context

The factual graph is navigation and evidence infrastructure, not a prompt dump.
M3 ranks candidates as mandatory, required, useful, optional, or excluded. It
always retains critical binding instructions, but it limits references by role,
relevance, freshness, coverage, redundancy, and budget. Large material should
be represented by a source-linked retrieval handle when it is not necessary in
full.

Every packet records included sources and omitted candidates with a reason.
Role views must genuinely differ: a planner needs problem framing and impact
evidence; a worker needs permitted scope and implementation context; a reviewer
and verifier need requirements/evidence-facing material without inheriting a
worker's private reasoning. If more context becomes necessary, a structured
expansion request yields a linked supplemental packet. The initial packet never
changes.

## Harness boundary

M3 may hand a canonical packet to Codex, Claude Code, or another
provider-neutral planning harness. The harness may return a technical plan or
request more context. Its output is versioned generated evidence tied to exact
inputs, model/harness configuration, timestamps, and an output hash.

The harness cannot modify the mission, make an approval, create M4
requirements, launch work, or accept work. Timeouts, refusals, malformed
results, stale packets, cancellations, and duplicate requests leave durable
M3 state intact and explainable.

## What success looks like

For identical versions of the origin, workspace model, graph snapshot, task
position, role, and compiler configuration, M3 must produce the same canonical
packet structure and content hash. A reviewer must be able to trace every
mission field to human input, approved knowledge, durable authority, factual
evidence, or clearly labelled inference.

The system should refuse to hide uncertainty: incomplete graph coverage,
unresolved terms, stale sources, budget truncation, insufficient authority,
and material ambiguity must appear in the output and affect readiness. No
packet may include unrestricted repository retrieval or silently convert source
text into instructions.

M3 also has an empirical bar. It will compare ordinary agent search, typed
intake plus cheap sentinels, bounded graph retrieval, and task-local probes
under equivalent conditions. A richer stage is enabled only if it improves on
the cheaper baseline without concealing high-risk false negatives. Otherwise it
remains experimental or disabled.

## Current state and implementation order

M3 is ready to begin, but its implementation has not started. M2 is closed
except for the separately deferred Buzz adapter (M2-009); its M2-011 handoff
and factual-graph closeout are accepted. M3-000 is the only ready M3 task. It
must validate the accepted contracts and preregister the benchmark before any
M3 feature work begins.

M3 starts from pinned schemas and fixtures for origins, source manifests,
workspace models, graph snapshots, bounded queries, sentinels, provenance,
coverage, errors, and omissions. The handoff documents both supported behavior
and residual limitations, including partial coverage and the rule that empty
results never prove absence.

The board then proceeds in order:

1. validate the handoff and preregister the quality benchmark;
2. define typed task contracts and readiness;
3. persist task positions, ambiguity, and decisions;
4. plan bounded factual context and optional interpretive probes;
5. select candidates and compile immutable role-specific packets;
6. compile governed mission proposals;
7. add expansion and planning-harness handoff; and
8. run the benchmark and publish M4's handoff.

The detailed acceptance criteria, dependencies, and verification commands are
in [TASKS.md](TASKS.md), [GATES.md](GATES.md), and the individual task packets
under [tasks/](tasks/).

## Source map

- [M3 board README](README.md) — status, boundary, required reading, and agent
  start protocol.
- [M3 task index](TASKS.md) — implementation sequence and dependencies.
- [M3 decisions](DECISIONS.md) — fixed decisions about harness authority,
  probes, and minimum sufficient context.
- [Persistent codebase factual-graph design](../../../plans/2026-07-29-persistent-codebase-factual-graph-design.md)
  — M2/M3 graph boundary, record model, query constraints, and benchmark.
- [Deterministic context compiler specification](../../governance/05-context-compiler/specification.md)
  — precedence, packet structure, expansion protocol, and reproducibility
  requirements.
- [M2-to-M3 handoff task](../m2-human-collaboration-intake/tasks/M2-011-m2-contracts-m3-handoff.md)
  — the accepted prerequisite contract publication.
- [M2-to-M3 handoff](../m2-human-collaboration-intake/artifacts/m2-to-m3-handoff.md)
  — the required M3-000 validation checklist and fixture inventory.
- [M2 code-graph handoff](../m2-human-collaboration-intake/artifacts/m2-code-graph-m3-handoff.md)
  — factual graph query, coverage, provenance, and limitation contracts.
