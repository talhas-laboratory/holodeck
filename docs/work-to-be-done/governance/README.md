# Agentic governance implementation library

This library restructures the normative design specification into implementation-facing areas without changing its authority. It is an index and working reference, not a replacement for the source document.

Start with [the source record](00-source/README.md), then read [shared contracts](shared/README.md). Each numbered folder has both a concise `README.md` and a `specification.md` mechanical transcription of its full source section. The copied DOCX remains the final authority for visual layout and inline formatting.

## Navigation

| Folder | Proposal |
| --- | --- |
| `01-executive-design` | Operating flow, target service boundaries, and non-negotiable design rules |
| `02-shared-governance-model` | Identity, revisions, provenance, trust, evidence, actors, and events |
| `03-workspace-intelligence` | Workspace models, sources, context modules, freshness, approvals |
| `04-curation` | Structured workspace, task, and on-demand curation |
| `05-context-compiler` | Deterministic, role-specific immutable context packets |
| `06-work-graph-requirements-gates` | Task meaning, requirements, lifecycle gates, and traceability |
| `07-test-planning` | Failure models, test oracles, independent verification |
| `08-work-evidence-learning` | Traces, worklogs, completion candidates, recovery, learning |
| `09-agent-adapters-enforcement` | Controlled execution, completion protocol, CI backstop |
| `10-review-loop` | Revision-based review, findings, re-review, escalation |
| `11-integrated-lifecycle` | The complete governed task lifecycle and failure paths |
| `12-roadmap` | Phased delivery order and exit conditions |
| `13-system-acceptance` | Product-level definition of done |
| `appendices` | Canonical object inventory, event catalogue, worked example, and checklist |

Cross-cutting schemas, APIs, and events live in `shared/`; they are not duplicated as competing definitions inside proposal folders.
