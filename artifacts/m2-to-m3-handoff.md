# M2 → M3 consolidated handoff

**Published by:** M2-011  
**For:** an independent M3 agent starting M3-000  
**Date:** 2026-07-29  
**Verified commit:** `322317816bb83721b2ec361cb3f66e704cf0e4c3`  
**Companion index:** `artifacts/m2-contracts-index.md`  
**Companion evidence:** `artifacts/m2-consolidated-acceptance-evidence.md`  
**Graph handoff (must read):** `artifacts/m2-code-graph-m3-handoff.md`

This document is the milestone close for M2 publication. It is sufficient to
begin M3-000 without any prior chat context. It does **not** implement M3
features and does **not** unblock Buzz (M2-009 remains gated).

---

## 1. Authority boundary

### What M2 owns (fact / intake / workspace evidence)

- Collaboration ingress contracts, authenticated actor mapping, durable inbound
  receipts, task origins, conversation context manifests, outbound status via
  durable outbox.
- Workspace bindings, discovery, reversible genesis proposals + human decide.
- Workspace intelligence: model, sources, observations, modules, gaps,
  decisions, readiness/trust, curation/activation, refresh/stale/query.
- Revision-scoped **factual** repository graph: entities, relations,
  provenance, coverage, bounded queries, high-recall sentinels.

### What M3 must not treat as fact or authority

- Task origins ≠ missions, runs, approvals, or acceptance.
- Outbound delivery acknowledgement ≠ proof of downstream processing.
- Workspace readiness / GOVERNED activation ≠ permission to compile binding
  missions or launch agents.
- Graph facts ≠ complete runtime behavior; coverage may be partial/unknown.
- Extractor observation methods and provider output are **data**, not
  instructions or prompt authority.
- Sentinel `UNRESOLVED` / empty queries ≠ risk cleared.
- M3 hypotheses, interpretive probes, ranked context, and packets are
  **task-local M3 records** — never write them back as M2 graph facts.
- GitNexus research notes ≠ production Holodeck model.
- Buzz is **not** published; do not assume live provider ingress.

M3 owns typed task intake, positioning, task-local interpretation, factual
context planning, selection, immutable packets, mission proposals, and
planning-harness handoff — after M3-000 validates this packet.

---

## 2. Guarantees vs partial / unsupported (honest)

### Guarantees (implemented and tested)

- CIS intake outcomes through the **memory** harness (M2-010).
- Idempotent receipts/origins; tenant-coupled bindings; correlated outbound.
- Conversation context manifests persisted with origins (M2-018); provider
  thread fetch may be partial / fail-open with omission entries.
- Explainable discovery; claim-first HUMAN genesis decide.
- Intelligence persistence + curation activation with evidence-derived
  readiness ceilings and HUMAN decisions for governed+.
- Immutable source observations; selective stale propagation; intelligence
  query snapshot.
- Code-graph schema v1 family on governance migration **v24**; one ACTIVE
  snapshot per binding; fail-closed partial/mismatch; incremental≡full on
  fixture; bounded queries + never-cleared sentinels.

### Partial

- Python stdlib AST coverage is honest-partial (dynamic/multi-language/deep
  analysis gaps; structural P/R vs golden notes in M2-026 evidence).
- Classification heuristics for source discovery are conservative/path-based.
- Typed `collaboration.*` / intelligence command handlers may remain deferred
  behind application services + repositories.

### Unsupported / gated

- **Buzz adapter (M2-009)** — gated; not ready.
- GitNexus as production dependency — **not allowed** without commercial
  license decision.
- Partial snapshot activation — no durable policy-decision seam in M2.
- HTTP/CLI for code-graph queries — omitted; consume application DTOs.
- M3 interpretation, packets, missions, requirements, execution, acceptance.

---

## 3. End-to-end fixture path

Concrete path an M3 agent can reconstruct in tests (module / API names):

```text
1. Origin
   CollaborationIntakeOrchestrator + InMemoryCollaborationAdapter
   → CollaborationApplicationService.accept_task_origin
   → TaskOrigin (m2.task_origin.v1) + conversation_context_manifest

2. Workspace
   discover_workspace / propose_workspace_genesis / decide_workspace_genesis
   → repository + collaboration location bindings (m2.repository_binding.v1, …)

3. Intelligence
   open_workspace_intelligence_app
   → discover_and_register_sources → HUMAN WorkspaceDecision
   → activate_curation → query_workspace_intelligence
   (acceptance: tests/test_m2_017_onboarding_refresh_acceptance.py)

4. Repo binding + snapshot
   Active repository binding on workspace
   → open_code_graph_ingestion_app
   → CodeGraphIngestionService.build_graph(GraphBuildRequest)
   Fixture tree: tests/fixtures/code_graph/python_reference
   rev_a = fixture:c059dce6bb6c4dfa257e2cc1d5d737089fea940091e57090d268dc6dae2c21bb
   rev_b = fixture:9714592f9bbc4b5c5a7b2548d52d57e88d5af1d43e6e27ac0a9864e0a3ec021e

5. Bounded query
   open_code_graph_query_app → CodeGraphQueryService
   find_entities / get_neighbors / traverse_paths / get_change_neighborhood
   / get_sources_for_facts / compare_snapshots
   Seeds: sample_app.service.Greeter; sample_app.api.handle_greet;
   schema/manifest/config/migration paths in graph handoff §8

6. Sentinels
   CodeGraphQueryService.evaluate_sentinels
   → ACTIVATED | UNRESOLVED only
```

Changed paths `rev_a` → `rev_b`: `sample_app/service.py`, `tests/test_api.py`,
`tests/test_service.py`.

Full acceptance glue: `tests/test_m2_code_graph_acceptance.py`.

---

## 4. Graph handoff by reference (must-read)

Do **not** duplicate the full graph document. Read
`artifacts/m2-code-graph-m3-handoff.md` sections:

| § | Topic |
| --- | --- |
| 1 | Graph schema versions + migration v24 |
| 2 | Active vs historical snapshot rules |
| 3 | `CodeGraphIngestionService` / `CodeGraphQueryService` seams |
| 4 | Bounded query contracts (`QueryBudget`, omissions) |
| 5 | Sentinel contracts (never cleared) |
| 6 | Trust / freshness / provenance |
| 7 | `CodeGraphReason` / coverage / truncation vocabulary |
| 8 | Fixture ids and query seeds |
| 9 | Non-negotiable rules for M3 |
| 10 | Benchmark arms A–D preregistration |
| 11 | GitNexus research-only |
| 12 | Partial coverage honesty |

Acceptance: `artifacts/m2-code-graph-acceptance-evidence.md`.

---

## 5. Collaboration / task-origin / context-manifest contracts M3 needs

| Contract | Schema / path | Seam |
| --- | --- | --- |
| Endpoint / actor mapping / receipt | `m2.collaboration_endpoint.v1`, `m2.external_actor_mapping.v1`, `m2.inbound_event_receipt.v1` | `open_collaboration_app` |
| Task origin | `m2.task_origin.v1` | `accept_task_origin` |
| Conversation context manifest | entries on origin via `build_conversation_context_manifest` | persisted with origin; M2-018 |
| Outbound status | `m2.outbound_collaboration_message.v1` | `enqueue_outbound_status` |
| Adapter port | `CollaborationAdapter` | memory harness only in CI |

M3 may assume durable origins + manifests as **inputs**. It must not invent a
Buzz-backed thread API; live fetch remains M2-009.

Design/test specs: `docs/plans/2026-07-27-m2-collaboration-intake-design.md`,
`docs/plans/2026-07-27-m2-collaboration-intake-test-specification.md`.

---

## 6. Readiness / trust / freshness semantics

- **TrustClass** and promotions require HUMAN `WorkspaceDecision` where
  curation demands it; boolean shortcuts are not authorization.
- **ReadinessLevel** ceilings are **derived from durable evidence**;
  `record_readiness_assessment` is the shared write gate. Governed+ needs
  typed `authorized_readiness_level` on a HUMAN readiness decision.
- **Freshness:** new immutable observations; refreshing an existing
  repository-file source marks it STALE and propagates STALE only to context
  modules that list that source (M2-016; proven in M2-017 / M2-026).
- Graph snapshot freshness is revision + observation scoped; superseded
  ACTIVE snapshots remain historically queryable by `snapshot_id`.

---

## 7. Empty result ≠ cleared; hypotheses ≠ facts; extractor data ≠ instructions

1. Empty graph/query results and sentinel `UNRESOLVED` mean **insufficient
   evidence**, never cleared risk.
2. M3 task-local hypotheses and interpretive probes are separate records; never
   promote them into M2 entity/relation facts.
3. Extractor output / observation methods (`direct_parse`, etc.) are data only.
   No provider prompt, interpretation, or instruction authority enters M2
   domain events or may be silently elevated by M3.

---

## 8. Error / omission / coverage vocabulary pointers

- Graph: `CodeGraphReason` codes and `CoverageStatus`
  (`complete` | `partial` | `unknown`) — handoff §7.
- Query truncation: `QueryOmissions.reasons` (`max_depth`, `max_results`,
  `max_visited_nodes`).
- Diagnostics: e.g. `unresolved_dynamic_call` (never a `CALLS` edge).
- Collaboration: `VerificationResult`, `ProcessingOutcome`,
  `CollaborationAdapterAuthError` (CIS-001; no receipt).
- Conversation manifests: omission entries for partial thread capture.
- Intelligence: gap/contradiction/decision schemas in contracts index.

---

## 9. Benchmark arms A–D (preregister for M3-000 to lock)

From graph handoff §10 — **preregistered here for M3-000 to lock** before any
agent-quality run (do not move thresholds after observing results):

```text
A. ordinary agent search
B. A + typed task intake and cheap sentinels
C. B + bounded factual-graph retrieval
D. C + task-local interpretive probes
```

Primary metrics (proposed; lock numbers in M3-000): accepted patch rate;
consequential affected-component recall; regression and high-risk FN rate
(report high-risk FNs separately); required-test and invariant coverage.

Promotion logic (proposed): graph justified only if **C beats B**; interpretive
probes only if **D beats C**. Exact numeric thresholds are **M3-000's lock**.

---

## 10. Blockers for M3

| Item | Blocks M3-000? |
| --- | --- |
| M2 contracts index + this handoff + graph handoff | Required — **published** |
| Buzz (M2-009) | **No** — not required for M3-000 |
| M1-024/025 human milestone acceptance | Does not block M3 contract validation against reviewed M1/M2 code |
| Partial activation policy seam | Not required for M3-000; treat partial as fail-closed |
| GitNexus license | N/A — research-only; do not depend |

If M3-000 finds a missing **stable input**, record it as a blocker; do not
patch around it inside M3.

---

## 11. Exact verification commit + how to run tests / package

**Commit:** `322317816bb83721b2ec361cb3f66e704cf0e4c3` (stamped after publish commit).

```bash
uv run --extra dev pytest -q
uv build
uvx twine check dist/*
```

Focused smoke:

```bash
uv run --extra dev pytest -q \
  tests/test_m2_011_handoff_artifacts.py \
  tests/test_m2_e2e_memory_intake.py \
  tests/test_m2_017_onboarding_refresh_acceptance.py \
  tests/test_m2_code_graph_acceptance.py
```

Composition entrypoints: `holodeck_governance.composition`.

---

## 12. "No hidden conversation context" checklist for M3-000 start

An independent builder can start M3-000 if they have read, in order:

- [ ] This file (`artifacts/m2-to-m3-handoff.md`)
- [ ] `artifacts/m2-contracts-index.md`
- [ ] `artifacts/m2-consolidated-acceptance-evidence.md`
- [ ] `artifacts/m2-code-graph-m3-handoff.md` (§1–12)
- [ ] `artifacts/m2-code-graph-acceptance-evidence.md`
- [ ] M3 board: `docs/work-to-be-done/taskboards/m3-context-and-mission-compilation/README.md`
- [ ] M3-000 packet: `.../tasks/M3-000-entry-handoff-and-benchmark-protocol.md`
- [ ] Product vision briefly: `docs/product-vision/{README,PRODUCT_VISION,DECISION_GUIDE}.md`
- [ ] Factual graph design: `docs/plans/2026-07-29-persistent-codebase-factual-graph-design.md`
- [ ] Pinned verification commit above + can run pytest/package locally

No Slack/chat thread, agent transcript, or unpublished board note is required.

M3-000 still must **validate** contracts, build the entry matrix, and **lock**
benchmark protocol artifacts — handoff readiness ≠ M3-000 done.

---

## Related board paths

- M2 artifacts index:
  `docs/work-to-be-done/taskboards/m2-human-collaboration-intake/artifacts/`
- M1 prior pattern:
  `docs/work-to-be-done/taskboards/m1-governance-kernel/artifacts/m1-contracts-migration-m2-handoff.md`
