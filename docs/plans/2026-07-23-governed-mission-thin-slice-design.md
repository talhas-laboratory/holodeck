# Governed mission thin slice

## Decision

Add a versioned governed-mission workflow alongside the existing workspace/task/run coordination API. Do not reinterpret existing runs as missions or alter their lifecycle semantics.

## Hybrid authority model

An LLM curator is an external proposal producer, accessed through a provider-neutral structured proposal API. It may propose source-linked workspace context, delegation contracts, requirements, and risks. The runtime never accepts free-form text as authority: it validates identifiers, source references, trust/status fields, and payload shape; records curator/model metadata; and requires explicit approval before a proposal becomes a binding contract or mission input.

This lets MCP-capable or API-based agents act as curators without binding Holodeck to one model provider or storing a provider credential in the local runtime.

## First vertical slice

1. Register immutable workspace sources.
2. Submit source-linked curator proposals for a task.
3. Approve a delegation contract and requirement set.
4. Compile an immutable mission packet with a stable content hash.
5. Create a completion candidate and attach requirement-linked evidence.
6. Let the gate service issue an accepted/rejected decision only when the mission has approved requirements and evidence for every requirement.

## Deliberate exclusions

No live model-provider credential integration, automatic source crawling, environment compiler, controlled worker launcher, independent review, or CI merge gate in this slice. These follow once the durable authority and evidence boundary is proven.

## Verification

Use a live HTTP test to prove the complete path and regression tests that reject unapproved proposals, mission mutation, missing source provenance, missing evidence, and duplicate final decisions.
