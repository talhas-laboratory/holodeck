# M2-014 — Implement repository/source discovery and trust classification

**Status:** done
**Owner:** cursor
**Depends on:** M2-012, M2-013

## Outcome

Invent `WorkspaceSource` records from bound-repo path observations with
conservative, deterministic trust classification. Discovery never grants
instruction authority.

## In scope

- Domain `discovery.py`: `ObservedSourcePath`, `DiscoveredSourceCandidate`,
  `classify_observed_path`, `invent_sources_from_observations`.
- Path heuristics: README/docs → document/ordinary; `.github`/ci →
  trusted_observation; tests → test_result; source → repository_file/untrusted;
  manifests → ordinary repository_file.
- Application `discover_and_register_sources` requiring
  `workspace.intelligence.curate`, registering via existing `register_source`,
  and skipping natural-key conflicts (idempotent rediscovery).
- Explicit observations API (no binding enumeration required).
- Tests for heuristics, no instruction_authority, rediscovery skip, curate
  permission, cross-tenant deny, and no mission/run creation.

## Non-goals

- Curator approval/activation product flow (M2-015).
- Freshness query APIs (M2-016).
- Full onboarding/refresh E2E proof (M2-017).
- Buzz ingress (M2-009, gated).
- Automatic filesystem walks or remote git inventory jobs.

## Required invariants

- Discovery never invents `instruction_authority`, `authoritative_reference`,
  or `generated_interpretation` trust.
- Registered sources from discovery always have `instruction_authority=False`.
- Natural-key conflict skips the existing source rather than failing the batch.
- Mutating discovery requires `workspace.intelligence.curate`.
- Cross-tenant workspace references are rejected.
- No mission or run objects are created.

## Acceptance criteria

- A curator can submit observed paths and receive registered + skipped counts.
- Classification is deterministic from path patterns / optional kind hints.
- Rediscovery of the same locator is idempotent.

## Verification

```text
uv run --extra dev pytest -q tests/test_m2_workspace_source_discovery.py
uv run --extra dev pytest -q
```

## Evidence and handoff

Verification completed 2026-07-29:

- `uv run --extra dev pytest -q tests/test_m2_workspace_source_discovery.py` → **7 passed**
- `uv run --extra dev pytest -q` → **358 passed in 36.05s**

Changed artifacts:

- `src/holodeck_governance/domain/workspace/intelligence/discovery.py`
- `src/holodeck_governance/domain/workspace/intelligence/__init__.py`
- `src/holodeck_governance/application/workspace_intelligence.py`
- `tests/test_m2_workspace_source_discovery.py`
- this task packet and the M2 board index/lanes/updates/decisions
- `docs/plans/2026-07-27-workspace-model-and-intelligence-design.md` status line

Next ready task: **M2-015** — workspace curation, approval, activation, and
readiness (Buzz remains gated at M2-009).

## Residual risks

- Classification heuristics are path-based and intentionally conservative;
  curators must promote trust explicitly (M2-015).
- Freshness/query APIs and onboarding E2E remain M2-016..017.
- Buzz ingress remains gated (M2-009).
