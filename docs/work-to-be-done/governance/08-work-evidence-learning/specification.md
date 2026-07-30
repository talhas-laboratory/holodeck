# 8. Worklog, evidence, and organizational learning

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 8. Worklog, evidence, and organizational learning

Holodeck needs a smart documentation system, but it must not pretend to capture a model’s private chain of thought. The correct design is a structured work-evidence and learning system that combines automatic traces, concise decision-relevant agent records, and a controlled promotion pipeline into durable knowledge.

### 8.1 Three-layer documentation model

| Layer | Contents | Trust treatment |
| --- | --- | --- |
| Automatic execution trace | Tool calls, commands, files, diffs, tests, errors, timestamps, approvals, context packet, commits. | Observed fact within the instrumentation boundary. |
| Agent work journal | Plan, assumptions, decisions, expected outcomes, failure interpretations, strategy changes, uncertainty, recovery. | Agent-authored claim; must link to evidence. |
| Durable workspace knowledge | Confirmed decisions, failure patterns, recovery procedures, invariants, test strategies, superseded assumptions. | Promoted only after validation and versioning. |

### 8.2 What to record automatically

- Agent identity, role revision, model/tool metadata, run ID, task ID, context packet IDs, and starting repository revision.
- Tool invocations and normalized results.
- Commands, exit codes, stdout/stderr references, and test classification.
- Files read when observable, files changed, diff snapshots, commits, and generated artifacts.
- Permission requests, approvals, denials, and overrides.
- Errors, timeouts, interruptions, resource limits, and adapter lifecycle events.
- Ending repository state and uncommitted changes.
### 8.3 Agent-authored checkpoints

Do not force constant narration. Require structured records at meaningful points:

- Initial execution plan and known assumptions.
- A significant decision or architecture trade-off.
- A failed attempt or unexpected result.
- A strategy change and its evidence.
- Discovery of an unplanned dependency or scope gap.
- A request for context, permission, or human input.
- A recovery action after failure or interruption.
- Submission for review or verification.
- Handoff, interruption, cancellation, or final completion candidate.
### 8.4 Worklog event schema

```text
WorklogEvent
  id
  task_id
  run_id
  candidate_revision_id
  actor_id
  actor_role_revision
  event_type              # plan, assumption, decision, observation, failure,
                          # hypothesis, strategy_change, recovery, risk, handoff
  timestamp
  objective
  observed_facts[]        # evidence refs only
  interpretation
  confidence
  related_requirements[]
  related_files_or_symbols[]
  evidence_refs[]
  next_action
  unresolved_questions[]
  supersedes[]
  sensitivity
  validation_status
```

### 8.5 Completion candidate

A worker cannot declare completion. It submits a structured candidate that the runtime and reviewers validate.

```text
CompletionCandidate
  id
  run_id
  candidate_revision_id
  requirements_addressed[]
  implementation_summary[]
  decisions[]
  failed_attempts[]
  strategy_changes[]
  files_changed_claimed[]
  tests_claimed[]
  evidence_refs[]
  known_limitations[]
  remaining_risks[]
  unresolved_questions[]
  rollback_strategy
  continuation_strategy
  context_gaps[]
  submitted_at
```

### 8.6 Validate narrative against trace

| Worker claim | Runtime check | Disposition |
| --- | --- | --- |
| “All tests passed.” | Verify test commands and results exist. | Reject or flag if unsupported. |
| “Only these files changed.” | Compare against repository diff. | Require correction if incomplete. |
| “Requirement X is satisfied.” | Check linked evidence and coverage. | Gate fails if evidence is absent. |
| “No unresolved failures.” | Inspect failing commands/tests and open findings. | Reject contradictory submission. |
| “Failure caused by Y.” | Check supporting logs/tests/reviewer confirmation. | Store as interpretation until supported. |

### 8.7 Interrupted runs

Agents may crash, time out, disconnect, or be stopped before submitting documentation. Holodeck must still produce an incomplete-run record from observed evidence.

```text
InterruptedRunSummary
  last_observed_action
  current_repository_diff
  commands_and_tests_executed[]
  errors[]
  active_permissions_and_claims[]
  available_worklog_events[]
  missing_submission_fields[]
  likely_recovery_point
  suggested_next_role
  status = interrupted
```

### 8.8 Promotion into durable knowledge

```text
raw observation
  -> agent interpretation
  -> supporting evidence
  -> verifier/reviewer confirmation
  -> human approval when policy requires
  -> promoted knowledge revision
```

| Knowledge status | Meaning |
| --- | --- |
| unverified | Generated or asserted but not sufficiently supported. |
| supported | Evidence exists but independent confirmation or approval is incomplete. |
| verified | Validated and eligible for authoritative workspace use. |
| disputed | Conflicting evidence or reviewer disagreement exists. |
| superseded | Replaced by a newer validated record. |
| archived | Retained for history but excluded from active context. |

### 8.9 Retention, sensitivity, and noise control

- Apply secret and personal-data redaction before durable storage where possible.
- Classify artifacts by sensitivity and restrict access to traces, prompts, logs, and generated summaries accordingly.
- Retain high-value decisions, failures, evidence, and handoffs longer than low-level repetitive telemetry.
- Create summaries and retrieval indexes, but keep originals where policy allows.
- Agents MUST be allowed to state uncertainty or unknown cause; do not force fabricated explanations.
### 8.10 Minimum APIs

```text
POST /runs/{run}/worklog-events
GET  /runs/{run}/trace
POST /runs/{run}/completion-candidates
POST /runs/{run}/interrupt
GET  /tasks/{task}/work-history
POST /knowledge-candidates/{id}/validate
POST /knowledge-candidates/{id}/promote
POST /knowledge/{id}/supersede
```

### 8.11 Acceptance criteria

- A run can be reconstructed from its packet, trace, worklog, candidate revisions, tests, and review history.
- Unsupported worker claims are detected before acceptance.
- Interrupted work remains recoverable without a graceful agent final response.
- Temporary agent interpretations never silently become workspace instructions.
- A validated failure can be promoted into a recovery procedure, requirement, or regression-test candidate with provenance.
