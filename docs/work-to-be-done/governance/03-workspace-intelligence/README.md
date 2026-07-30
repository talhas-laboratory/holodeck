# Persistent workspace intelligence

## Purpose

Turn a workspace into a durable, inspectable model of the project, not a folder plus a goal string. It becomes the upstream input to requirements, context routing, review alignment, and learning.

## Required records

- `WorkspaceModel`: identity/purpose, users and stakeholders, product model, architecture map, principles and constraints, domain language, knowledge sources, decisions, and gaps.
- `WorkspaceSource`: source type/location/revision, owner, trust class, sensitivity, refresh policy, observation time, stale status, module tags, and instruction-authority flag.
- `ContextModule`: bounded reusable knowledge with approved instructions, references, applicability, freshness, and version.

## Rules

- All knowledge comes from a registered source or an explicitly marked generated interpretation.
- Generated summaries must link exact source revisions; original sources remain retrievable; conflicts stay explicit.
- New instruction authority, purpose, non-goals, risk posture, and binding principles require approval unless created by an authorized human.
- Source changes selectively mark dependent modules stale rather than forcing a full re-curation.

## Minimum outcomes

Onboarding produces a versioned workspace model, source registry, context modules, gaps, and provenance report. A user can inspect what Holodeck believes, why, and what remains uncertain; earlier model revisions reproduce earlier runs.
