# Deterministic context compiler

## Purpose

Compile approved workspace knowledge, task state, role contracts, policy, repository state, and curator recommendations into an exact run-specific packet. This is core governance infrastructure, not a prompt field.

## Mandatory packet content

Workspace identity and approved instruction revision; task position, scope, non-goals, requirements and acceptance conditions; role responsibilities/permissions/prohibitions; repository and candidate revision; evidence/submission schema; policy/approval conditions; provenance index and trust labels.

## Rules

- Workers, planners, implementers, reviewers, and verifiers receive role-distinct packets.
- Rank items mandatory, required, useful, optional, or excluded. Explain omissions and use source-linked retrieval for large material.
- Never summarize away critical requirements or binding instructions merely to save tokens.
- Packets are immutable, previewable for elevated-risk work, provenance-complete, and content-hashed with the run.
- Context expansion is a structured request and produces a linked supplemental packet, never a silent mutation.

## APIs and acceptance

Provide task context planning, run packet compilation, packet retrieval/preview, expansion request, and expansion decision APIs. Identical inputs/revisions must yield identical packet structure and hash; untrusted text must not override instruction authority.
