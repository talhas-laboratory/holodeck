# Front matter and document control

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

HOLODECK RUNTIME

Agentic Governance & Knowledge Architecture
Implementation Specification

Detailed implementation guidance for workspace intelligence, context compilation, requirements, tests, work evidence, agent enforcement, and review loops

Version 1.0
22 July 2026

Implementation status: Normative design specification

Explicit exclusion: foundational runtime correctness and security repairs identified during the initial repository review are not specified in this document.

## Document control

| Field | Value |
| --- | --- |
| Document purpose | Translate the agreed product and architecture decisions into implementation-ready instructions for the Holodeck execution agent. |
| Primary audience | Implementation agents, maintainers, reviewers, and product owners working on Holodeck Runtime. |
| Normative scope | All improvement areas discussed after the foundational repository-gap analysis, excluding the foundational repairs themselves. |
| Authority | This document captures the decisions reached in the conversation and should be treated as the baseline implementation contract until superseded. |
| Change policy | Changes must be versioned, linked to a decision record, and identify affected requirements, schemas, APIs, and migration implications. |

### Normative language

The terms MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used deliberately. MUST indicates a required implementation invariant. SHOULD indicates the expected default, with deviations requiring documented rationale. MAY indicates an optional extension.

### Scope exclusion

```text
Excluded from this specification
The initial repository review identified foundational issues involving concurrency, path safety, status validation, persistence integrity, authentication, request validation, deployment hardening, and shallow tests. Those issues remain prerequisites, but the user explicitly requested this document to cover every subsequent improvement area except that first category.
```

## Contents

1. 1. Executive design summary
1. 2. Shared domain and governance conventions
1. 3. Persistent workspace intelligence
1. 4. Workspace, task, and on-demand curation
1. 5. Deterministic context compiler
1. 6. Work graph, structured requirements, and gates
1. 7. Test planning and test generation
1. 8. Worklog, evidence, and organizational learning
1. 9. Agent adapters and enforceable completion protocol
1. 10. Structured reviewer-worker feedback system
1. 11. Integrated end-to-end lifecycle
1. 12. Implementation roadmap and dependency order
1. 13. Definition of done and system-level acceptance criteria
1. Appendices: canonical schemas, API surface, events, and worked example
