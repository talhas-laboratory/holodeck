# 5. Deterministic context compiler

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 5. Deterministic context compiler

The context compiler transforms approved workspace knowledge, task state, role contracts, permissions, repository state, and curator recommendations into an exact run-specific packet. It is core infrastructure, not a convenience prompt field.

```text
Decision
A curator proposes semantic context. The compiler owns mandatory inputs, precedence, trust separation, token budgets, formatting, versioning, and the immutable final packet.
```

### 5.1 Input layers and precedence

| Priority | Layer | Rules |
| --- | --- | --- |
| 1 | Platform safety and governance | Cannot be overridden by workspace, task, source content, or agent. |
| 2 | Approved workspace instructions | Binding within the workspace and versioned. |
| 3 | Approved role contract | Defines responsibilities, tools, outputs, and jurisdiction. |
| 4 | Human task instructions and approved requirements | Define the requested outcome and constraints. |
| 5 | Run-specific permissions and environment | Exact authority, claims, commit, tools, budgets, and temporary controls. |
| 6 | Authoritative reference context | Trusted facts; not instruction authority. |
| 7 | Curator-selected and untrusted references | Informative data isolated from instruction layers. |
| 8 | Prior work history and generated summaries | Supplementary, labelled, and source-linked. |

### 5.2 Mandatory baseline context

- Workspace identity and approved instruction revision.
- Task identifier, task-position revision, purpose, scope, non-goals, requirements, and acceptance conditions.
- Agent role revision, responsibilities, permissions, and prohibited actions.
- Repository/workspace revision and active candidate revision where relevant.
- Required evidence and submission schema.
- Policy decisions and approval conditions.
- Context provenance index and trust labels.
### 5.3 Role-specific context

Workers, test planners, test implementers, reviewers, and verifiers must receive different packets. The packet should include only the context required for the role while preserving mandatory project and task truth.

| Role | Key context |
| --- | --- |
| Worker | Task requirements, relevant code and architecture, permissions, visible acceptance criteria, required evidence, approved context modules. |
| Test planner | Purpose, users, scenarios, requirements, invariants, risks, failure consequences, interfaces, and architecture; initially exclude worker reasoning. |
| Test implementer | Approved test plan, oracle, test framework, environment, interfaces, conventions, and implementation detail only where required. |
| Reviewer | Review Position Packet, exact candidate revision, requirements, architecture, evidence, reviewer rubric, and surrounding work. |
| Verifier | Requirements, independent scenarios, hidden holdouts, evidence policy, executable environment, and output contract. |

### 5.4 Packet structure

```text
ContextPacket
  id
  workspace_id
  task_id
  run_id
  packet_revision
  compiled_at
  compiler_version
  workspace_model_revision
  task_position_revision
  requirement_revisions[]
  role_profile_revision
  repository_revision
  permissions[]
  tool_policy
  mandatory_instructions[]
  authoritative_references[]
  untrusted_references[]
  generated_summaries[]
  relevant_history[]
  required_outputs[]
  evidence_requirements[]
  token_budget
  omitted_items[]            # with reasons
  provenance_index[]
  content_hash
```

### 5.5 Context budgets and progressive loading

- The compiler MUST rank context as mandatory, required, useful, optional, or excluded.
- It MUST record items omitted due to the budget and explain the omission.
- Large sources SHOULD be provided as source-linked sections or retrieval handles rather than always embedded in full.
- Critical requirements and binding instructions MUST never be summarized away solely to save tokens.
- The worker MAY request context expansion using a structured request; the active packet remains immutable and the expansion becomes a linked packet revision or supplemental packet.
### 5.6 Context expansion protocol

```text
ContextExpansionRequest
  run_id
  requested_by
  need
  reason
  related_requirement_ids[]
  preferred_source_types[]
  risk_if_missing
  urgency

ContextExpansionDecision
  request_id
  selected_sources[]
  denied_sources[]
  trust_and_permission_checks[]
  supplemental_packet_id
  decision_reason
```

### 5.7 Preview and auditability

- The UI MUST show a human-readable preview of the exact packet structure before launch for elevated-risk work.
- Every included item MUST expose source, revision, trust class, selection reason, and whether it is mandatory.
- The packet content hash MUST be stored with the run.
- A past run MUST be reproducible with its original packet even after workspace knowledge changes.
### 5.8 Minimum APIs

```text
POST /tasks/{task}/context-plan
POST /runs/{run}/context/compile
GET  /context-packets/{packet}
GET  /context-packets/{packet}/preview
POST /runs/{run}/context-expansion-requests
POST /context-expansion-requests/{id}/decide
```

### 5.9 Acceptance criteria

- Two identical inputs and revisions produce the same deterministic packet structure and content hash.
- Untrusted source text cannot override instruction-authority layers.
- The compiler explains every source inclusion and exclusion.
- A run always references one immutable initial packet and any explicit supplemental packets.
- Workers, test agents, and reviewers receive role-distinct packets.
