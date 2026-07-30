# 1. Executive design summary

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 1. Executive design summary

The target system is not a prompt manager, a task tracker, or a comment layer. Holodeck is to become a governed runtime that converts project purpose into bounded agent work, records what actually happened, requires evidence before acceptance, supports independent review, and promotes only validated learning into durable workspace knowledge.

```text
Primary architectural decision
Holodeck MUST own the lifecycle around agents. Agents may propose plans, perform work, submit evidence, and respond to reviews. They MUST NOT be the authority that decides their own successful completion.
```

### 1.1 Canonical operating flow

```text
Workspace onboarding
  -> workspace intelligence and knowledge map
  -> task creation and task-position analysis
  -> structured requirements and verification plan
  -> definition gate
  -> deterministic context packet
  -> worker execution under a Holodeck adapter
  -> automatic trace + structured worklog
  -> completion candidate
  -> structured review and revision loop
  -> independent verification
  -> completion/release decision
  -> validated learning promotion
```

### 1.2 Non-negotiable design rules

- Persistent over ephemeral. Context curation should build durable workspace and task assets, not merely generate a hidden prompt for one run.
- Deterministic authority around probabilistic intelligence. LLM curators and reviewers may propose and interpret; deterministic services own precedence, permissions, state transitions, schemas, and acceptance gates.
- Facts, claims, and validated knowledge remain separate. Runtime traces are observed facts; agent explanations are claims; workspace knowledge becomes authoritative only after validation.
- Every accepted outcome is traceable. Purpose, requirements, context, execution, evidence, review, and acceptance must be connected through stable identifiers and versions.
- No invisible context mutation. Every run receives an immutable, previewable context packet with provenance.
- Review is revision-oriented. Findings attach to exact candidate revisions and remain open until explicitly resolved, withdrawn, accepted as risk, superseded, waived, or escalated.
- Agents submit; Holodeck completes. A process exiting successfully or an agent claiming success cannot move a task to accepted completion.
### 1.3 Target service boundaries

| Service / module | Primary responsibility |
| --- | --- |
| Workspace Intelligence | Persist project purpose, users, principles, sources, modules, decisions, gaps, and freshness. |
| Curation Service | Analyze workspaces and tasks; propose structured context, requirements, roles, risks, and missing information. |
| Context Compiler | Deterministically assemble immutable run packets from approved inputs and policy. |
| Work Graph & Requirements | Represent why work exists, how tasks relate, what must become true, and which evidence is required. |
| Gate Engine | Control readiness, execution, review, verification, acceptance, and release transitions. |
| Test Planning & Verification | Derive failure models and test strategies; generate and execute independent evidence. |
| Trace & Worklog | Capture observed actions and structured agent-authored decisions, failures, and recovery. |
| Agent Runtime Adapters | Launch or wrap external agents, constrain authority, and normalize telemetry and submissions. |
| Review Service | Manage immutable revisions, findings, responses, re-review, jurisdiction, and escalation. |
| Learning Promotion | Convert supported findings into versioned durable workspace knowledge. |
