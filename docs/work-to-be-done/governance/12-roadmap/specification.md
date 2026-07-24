# 12. Implementation roadmap and dependency order

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 12. Implementation roadmap and dependency order

The implementation sequence should preserve vertical usefulness while avoiding premature autonomous behavior. Foundational runtime repairs remain external prerequisites and are not repeated here.

### 12.1 Phase A — Shared records and work graph

- Implement common IDs, revisions, provenance, trust classes, actors, roles, evidence references, and append-only events.
- Implement work hierarchy, typed relationships, Task Position, Requirement, and Candidate Revision records.
- Implement schema versioning for all APIs and events.
Exit condition: Holodeck can represent why a task exists, what must become true, and which exact revision is under discussion.

### 12.2 Phase B — Workspace intelligence and curation

- Implement source registry, context modules, workspace model, knowledge gaps, and approval flow.
- Implement Workspace Curator and Task Curator with structured outputs and provenance.
- Implement selective refresh and stale-module propagation.
Exit condition: onboarding produces a reviewable project model, and task creation produces a reviewable Task Position and context plan.

### 12.3 Phase C — Context compiler

- Implement precedence, trust separation, role-specific packet templates, budgets, provenance index, packet hashing, preview, and supplemental packets.
- Integrate packet IDs and hashes into runs and reviews.
Exit condition: every role receives a reproducible immutable packet assembled by deterministic rules.

### 12.4 Phase D — Requirements, test plans, and gates

- Implement requirement lifecycle, approval, traceability, and gate policies.
- Implement TestPlan, FailureHypothesis, oracle, coverage, and evidence records.
- Implement gate evaluation reports with explicit pass/fail reasons.
Exit condition: tasks cannot begin or complete without structured meaning and required evidence plans.

### 12.5 Phase E — Trace, worklog, and completion protocol

- Implement normalized trace events and artifact storage.
- Implement structured worklog checkpoints, completion candidates, interruption summaries, and trace-consistency validation.
- Implement learning-candidate records without automatic promotion.
Exit condition: Holodeck can distinguish what happened, what the agent claims, and what remains unverified.

### 12.6 Phase F — Agent adapters and CI enforcement

- Implement the generic adapter interface and one fully controlled CLI adapter first.
- Add tool-specific adapters incrementally.
- Implement protected repository status checks and imported-work reduced-observability handling.
Exit condition: at least one worker agent can be launched, observed, and prevented from self-completing; external changes cannot merge without Holodeck gates.

### 12.7 Phase G — Review loop

- Implement review position packets, reviewer profiles, review requests, structured findings, anchors, per-finding responses, re-review, and escalation.
- Implement jurisdiction-based blocking and scope-correction requests.
Exit condition: a worker and reviewer can complete multiple revision cycles with no loss of finding history or task alignment.

### 12.8 Phase H — Independent verification and learning promotion

- Implement test planner, independent test agents, holdout storage, evidence coverage, and verification decisions.
- Implement promotion of validated failures, decisions, and recovery strategies into knowledge modules and regression tests.
Exit condition: accepted work is evidence-based, and validated experience improves future context and testing.

### 12.9 Avoid premature complexity

- Do not start with a graph database; typed relational edges are sufficient.
- Do not start with a vector database; begin with explicit sources, module tags, deterministic selection, and targeted retrieval.
- Do not make every task invoke expensive curation; use deterministic paths for narrow high-confidence work.
- Do not make generated summaries authoritative.
- Do not implement unrestricted multi-agent debate before findings, roles, and escalation states exist.
