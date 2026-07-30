# Workspace, task, and on-demand curation

## Purpose

Use model intelligence for semantic discovery without granting it authority to mutate binding instructions or acceptance state.

## Curator workflow

Workspace curation inventories and classifies sources, infers project model candidates, detects contradictions and gaps, proposes modules/roles, passes deterministic validation, routes binding changes for approval, then persists an approved revision and refresh events.

Task curation locates parent work and affected users, identifies scope/non-goals/dependencies/parallel work, proposes requirements/invariants/risks/evidence, selects context by role, recommends worker/reviewer jurisdictions, detects readiness blockers, and creates a versioned Task Position and Context Plan.

## Controls

- Require structured output, provenance, curator model/version, confidence, and explicit `unknown` or `not found` values.
- Reject unknown IDs, missing required fields, forbidden trust escalation, and incompatible role recommendations deterministically.
- Compare proposed and approved models in the UI.
- On-demand curation creates a supplemental context revision; it never rewrites an active packet.

## Acceptance

Task creation can yield a complete inspectable proposal without launching a worker; curators can block readiness for missing context; every selected source has a reason and provenance link.
