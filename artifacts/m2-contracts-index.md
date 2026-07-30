# M2 contracts index

**Published by:** M2-011
**For:** M3-000 and later M3 agents
**Date:** 2026-07-29
**Governance SQLite migrations:** through **v24**
**Verified commit:** `322317816bb83721b2ec361cb3f66e704cf0e4c3`
**Package:** `holodeck_governance` (composition in `holodeck_governance.composition`)

This index lists stable M2 capabilities with status, schema/module path,
primary application seam, verifying tests, and honesty notes. It is the
contract map for the consolidated handoff at `artifacts/m2-to-m3-handoff.md`.

Status vocabulary:

- **implemented** — verified in source and tests at the pinned commit
- **partial** — shipped with known honest gaps
- **unsupported / gated** — not published as ready for M3 production use

---

## Collaboration intake boundary + memory harness (M2-001 / M2-008)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `holodeck_governance.domain.collaboration` (adapter port, intake grammar, CIS catalog); schemas on records below |
| Primary seam | `CollaborationAdapter` protocol; `InMemoryCollaborationAdapter` (`adapters.collaboration`); `CollaborationIntakeOrchestrator` (`application.collaboration_intake`) |
| Tests | `tests/test_m2_collaboration_contract.py`, `tests/test_m2_memory_adapter_harness.py` |
| Notes | Provider-neutral boundary only. Buzz SDK types stay out of domain. Explicit intake grammar `@holodeck work: <subject>`. |

---

## Bindings, actor mappings, inbound receipts (M2-002)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.collaboration_endpoint.v1`, `m2.external_actor_mapping.v1`, `m2.inbound_event_receipt.v1`; migrations **v11–v14** |
| Primary seam | `open_collaboration_app` → `CollaborationApplicationService` (endpoint / mapping / receipt record) |
| Tests | `tests/test_m2_collaboration_bindings_receipts.py`, `tests/test_m2_release_blockers.py` |
| Notes | Receipts dedupe on `(tenant_id, provider, external_event_id)`. Duplicate → `duplicate_replay`. |

---

## Task origins + conversation context manifests (M2-003 / M2-018)

| Field | Value |
| --- | --- |
| Status | **implemented** (Buzz-backed thread fetch remains stub until M2-009) |
| Schema / modules | `m2.task_origin.v1` + `conversation_context_manifest` entries (`domain.collaboration.origins`); migration **v12** (+ attribution v14) |
| Primary seam | `CollaborationApplicationService.accept_task_origin` / `accept_task_origin_with_outbound`; `build_conversation_context_manifest` |
| Tests | `tests/test_m2_task_origins.py`, `tests/test_m2_conversation_context.py`, `tests/test_m2_018_messy_slack_thread_fixture.py` |
| Notes | Origin is not a mission/run/approval. Manifest is immutable capture of direct conversation context; `fetch_thread_context` is fail-open / partial with omission entries. |

---

## Outbound collaboration messages (M2-004)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.outbound_collaboration_message.v1`; migration **v15** |
| Primary seam | `CollaborationApplicationService.enqueue_outbound_status` (durable outbox correlation) |
| Tests | `tests/test_m2_outbound_delivery.py` |
| Notes | Adapter `publish_outbound` acknowledgement ≠ proof of downstream processing. |

---

## Workspace repository / location bindings (M2-005)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.repository_binding.v1`, `m2.collaboration_location_binding.v1`; `domain.workspace.bindings`; migrations **v16–v17** area |
| Primary seam | `CollaborationApplicationService` workspace binding APIs (via collaboration repository) |
| Tests | `tests/test_m2_workspace_bindings.py` |
| Notes | Bindings are locators + eligibility inputs, not intelligence completeness. |

---

## Workspace discovery (M2-006)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `domain.workspace.discovery.evaluate_workspace_discovery` |
| Primary seam | `CollaborationApplicationService.discover_workspace` |
| Tests | `tests/test_m2_workspace_discovery.py` |
| Notes | Deterministic, explainable eligibility. Does not create workspaces. |

---

## Genesis proposals / decide (M2-007)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.workspace_genesis_proposal.v1`, events `m2.workspace.genesis.event.v1` |
| Primary seam | `propose_workspace_genesis` / `decide_workspace_genesis` (HUMAN decide; claim-first) |
| Tests | `tests/test_m2_workspace_genesis.py` |
| Notes | Creation remains reversible proposal until authorized human decision. |

---

## E2E intake (M2-010)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Composes M2-001–008 contracts via memory harness |
| Primary seam | `CollaborationIntakeOrchestrator` + `InMemoryCollaborationAdapter` + `CollaborationApplicationService` |
| Tests | `tests/test_m2_e2e_memory_intake.py` (**7** scenarios; CIS-001..008) |
| Notes | Auth refusal, reject, duplicate replay, cross-tenant, non-intake, happy-path correlated outbound — **no** mission/run. |

---

## Workspace intelligence model / sources / modules / gaps / readiness / trust (M2-012 / M2-013)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.workspace_model_revision.v1`, `m2.workspace_source.v1`, `m2.workspace_source_observation.v1`, `m2.context_item.v1`, `m2.context_module.v1`, `m2.knowledge_gap.v1`, `m2.contradiction.v1`, `m2.workspace_decision.v1`, `m2.workspace_readiness_assessment.v1`; domain under `domain.workspace.intelligence.*`; migrations **v19–v22** |
| Primary seam | `open_workspace_intelligence_app` → `WorkspaceIntelligenceApplicationService` |
| Tests | `tests/test_m2_workspace_intelligence_contract.py`, `tests/test_m2_workspace_intelligence_persistence.py` |
| Notes | Typed intelligence command handlers may still be deferred (bootstrap/admin persistence exception). Readiness ceilings are evidence-derived. |

---

## Source discovery / trust (M2-014)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Source invention helpers + trust classes on `WorkspaceSource` |
| Primary seam | `WorkspaceIntelligenceApplicationService.discover_and_register_sources` (`intelligence.curate`) |
| Tests | `tests/test_m2_workspace_source_discovery.py` |
| Notes | Path-based conservative heuristics; promotion is curation (M2-015). |

---

## Curation / activation (M2-015)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.workspace_curation_proposal.v1`; HUMAN `WorkspaceDecision` for trust/readiness |
| Primary seam | `activate_curation` (single transaction: promotions, approve, readiness) |
| Tests | `tests/test_m2_workspace_curation.py` |
| Notes | Governed+ readiness needs HUMAN `readiness_decision_id` with typed `authorized_readiness_level`. |

---

## Refresh / stale / query intelligence (M2-016)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Immutable observations (migration **v21**); stale propagation helpers |
| Primary seam | `refresh_sources`, `propagate_source_stale`, `query_workspace_intelligence` |
| Tests | `tests/test_m2_workspace_refresh_query.py` |
| Notes | New observation on existing source marks source stale and only modules that list that source. |

---

## Onboarding acceptance (M2-017)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Composed intelligence surface |
| Primary seam | `WorkspaceIntelligenceApplicationService` E2E world |
| Tests | `tests/test_m2_017_onboarding_refresh_acceptance.py` (**1** scenario) |
| Notes | onboard → discover → reject assured bypass → resolve gap → HUMAN decisions → activate GOVERNED → refresh → query; no Mission/Run. |

---

## Factual graph contracts / fixture (M2-019)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `m2.code_graph.v1` family (`CODE_*_SCHEMA_VERSION` constants in `domain.workspace.intelligence.code_graph.types`); closed `EntityKind` / `RelationKind` |
| Primary seam | Domain contracts + golden fixture under `tests/fixtures/code_graph/python_reference` |
| Tests | `tests/test_m2_code_graph_contract.py` |
| Notes | Unknown kinds rejected. Fixture revisions: `rev_a` / `rev_b` (`fixture:<content_hash>`). |

---

## Extractor port + `python_stdlib_ast` (M2-020 / M2-022) — GitNexus research-only

| Field | Value |
| --- | --- |
| Status | **implemented** (selected provider); GitNexus **unsupported** for production |
| Schema / modules | `RepositoryExtractor` port; `PYTHON_AST_PROVIDER_SCHEMA` = `m2.python_stdlib_ast.v1`; assessment `artifacts/m2-code-graph-provider-assessment.md` |
| Primary seam | `PythonStdlibAstExtractor` (`adapters.code_graph.python_ast`); wired by `open_code_graph_ingestion_app` |
| Tests | `tests/test_m2_repository_extractor_contract.py`, `tests/test_m2_python_extractor.py` |
| Notes | **GitNexus is research-only** (PolyForm Noncommercial). Do not treat as a production dependency. Dynamic calls → diagnostics only. Metrics: `artifacts/m2-022-python-extractor-metrics.json`. |

---

## Graph SQLite persistence migration 23 / 24 (M2-021 + foundation)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Migrations **v23** (immutable graph tables) + **v24** (observation-scoped uniqueness, provenance coupling, claim leases) |
| Primary seam | `SqliteCodeGraphRepository` (storage only; M3 must not import from packet compilers) |
| Tests | `tests/test_m2_code_graph_migrations.py`, `tests/test_m2_code_graph_persistence.py` |
| Notes | At most one ACTIVE snapshot per `(tenant, workspace, repository_binding)`. Facts insert-immutable; membership reuse across snapshots. |

---

## Ingestion / activation (M2-023)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Event payload `m2.workspace.code_graph.event.v1`; build claims / receipts |
| Primary seam | `open_code_graph_ingestion_app` → `CodeGraphIngestionService.build_graph` / `get_status` |
| Tests | `tests/test_m2_code_graph_ingestion.py`, `tests/test_m2_code_graph_failure_recovery.py` |
| Notes | Requires `intelligence.curate`. Partial cannot activate (no durable policy-decision seam). Failed rebuild preserves prior active. |

---

## Incremental refresh (M2-024)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Domain plan/merge in code-graph incremental helpers; `GraphBuildRequest.changed_paths` + `base_snapshot_id` |
| Primary seam | `CodeGraphIngestionService.build_graph` (incremental path) |
| Tests | `tests/test_m2_code_graph_incremental_refresh.py` |
| Notes | Empty `changed_paths` with base → full fallback. Metrics: `artifacts/m2-024-incremental-refresh-metrics.json`. |

---

## Bounded queries + sentinels (M2-025)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | `domain.workspace.intelligence.code_graph.queries` / `sentinels`; `QueryBudget`, `SentinelKind` |
| Primary seam | `open_code_graph_query_app` → `CodeGraphQueryService` (read-only) |
| Tests | `tests/test_m2_code_graph_queries.py`, `tests/test_m2_code_graph_sentinels.py` |
| Notes | Sentinels are **ACTIVATED** or **UNRESOLVED** only — never cleared. Empty result ≠ cleared risk. Metrics: `artifacts/m2-025-code-graph-queries-metrics.json`. HTTP/CLI omitted. |

---

## Graph acceptance (M2-026)

| Field | Value |
| --- | --- |
| Status | **implemented** |
| Schema / modules | Full lifecycle over schema **v24+** |
| Primary seam | Composition of ingestion + query + intelligence refresh |
| Tests | `tests/test_m2_code_graph_acceptance.py` |
| Notes | Evidence: `artifacts/m2-code-graph-acceptance-evidence.md`, metrics JSON, graph handoff `artifacts/m2-code-graph-m3-handoff.md`. |

---

## Buzz adapter (M2-009) — gated

| Field | Value |
| --- | --- |
| Status | **gated / not published as ready** |
| Schema / modules | No production Buzz adapter module published |
| Primary seam | Would implement `CollaborationAdapter` for Buzz only after neutral contracts (already done) and live-ingress authorization |
| Tests | none for live Buzz |
| Notes | **Explicitly not ready.** M3-000 does **not** require Buzz. Memory harness proves CIS. See product Buzz strategy; production ingress remains deferred. |

---

## Composition roots (adapters may import; application must not)

| Function | Service |
| --- | --- |
| `open_governance_app` | `GovernanceApplicationService` (M1) |
| `open_collaboration_app` | `CollaborationApplicationService` |
| `open_workspace_intelligence_app` | `WorkspaceIntelligenceApplicationService` |
| `open_code_graph_ingestion_app` | `CodeGraphIngestionService` |
| `open_code_graph_query_app` | `CodeGraphQueryService` |

---

## Related artifacts

- Consolidated acceptance: `artifacts/m2-consolidated-acceptance-evidence.md`
- M2→M3 handoff: `artifacts/m2-to-m3-handoff.md`
- Graph-only handoff: `artifacts/m2-code-graph-m3-handoff.md`
