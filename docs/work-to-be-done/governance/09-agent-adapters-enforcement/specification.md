# 9. Agent adapters and enforceable completion protocol

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 9. Agent adapters and enforceable completion protocol

Prompt instructions alone cannot force Codex, Cursor, Claude Code, or another agent to document work reliably. Enforcement must arise because Holodeck controls the accepted workflow and withholds valuable state transitions until the required records and evidence exist.

```text
Core rule
Agents do not complete tasks. Agents submit work for completion. Holodeck validates the submission, evidence, reviews, and gates before marking the task accepted.
```

### 9.1 Enforcement hierarchy

| Mechanism | Strength | Use |
| --- | --- | --- |
| Prompt instruction | Weak | Communicate expectations; never rely on it for acceptance. |
| Repository/agent rules | Weak to moderate | Persistent guidance and schema reminders. |
| Tool hooks or permission callbacks | Moderate | Observe or block selected actions where supported. |
| Holodeck launcher/adapter | Strong | Own process lifecycle, packet delivery, telemetry, and submission. |
| Structured completion protocol | Strong | Prevent undocumented work from advancing. |
| Trace-to-claim validation | Very strong | Detect unsupported or contradictory documentation. |
| Repository CI/merge gate | Strongest practical backstop | Block acceptance even if local workflow is bypassed. |

### 9.2 Adapter interface

```text
AgentAdapter
  capabilities()
  prepare_environment(run, context_packet)
  configure_permissions(run, role_profile, policy)
  launch(run)
  stream_events(run)
  request_permission(run, action)
  capture_repository_state(run)
  request_checkpoint(run, checkpoint_type)
  request_completion_candidate(run)
  terminate(run, reason)
  collect_final_state(run)
  normalize_result(run)
```

### 9.3 Generic launcher workflow

1. Create or select an isolated workspace/worktree/container.
1. Record the starting repository revision and environment fingerprint.
1. Compile and store the immutable context packet.
1. Configure tools, permissions, budgets, and output schema.
1. Launch the external agent as a controlled process where possible.
1. Capture normalized stdout, stderr, tool events, files, commands, and test evidence.
1. Request structured worklog checkpoints at required lifecycle events.
1. On agent exit, do not infer task success from exit code.
1. Require or reconstruct a completion/interruption record.
1. Submit the candidate revision to review and gate evaluation.
### 9.4 Tool-specific integration strategy

| Integration mode | Preferred implementation |
| --- | --- |
| Programmatic CLI/API agent | Holodeck launches the process, passes packet and schema, restricts tools, captures structured output, and owns termination. |
| Agent with hooks/callbacks | Use hooks for action observation and permission checks; keep server-side acceptance independent of hooks. |
| Interactive editor agent | Use project rules for guidance, optional plugin/hooks for telemetry, and enforce completion through repository/CI gates. |
| Unsupported external execution | Treat imported changes as untrusted candidate revisions requiring explicit task association, trace limitations, review, and full verification. |

### 9.5 Completion transaction

The agent may submit a completion candidate, but the following server-owned sequence determines acceptance:

```text
candidate received
  -> schema validation
  -> trace consistency checks
  -> requirement/evidence coverage check
  -> candidate revision frozen
  -> review request created
  -> findings resolved
  -> independent verification
  -> gate engine decision
  -> accepted or returned for changes
```

### 9.6 Valuable actions gated by Holodeck

- Successful task completion.
- Accepted release of work ownership or task authority.
- Protected branch merge or accepted pull-request status.
- Deployment or production credential access.
- Promotion of worklog content into authoritative knowledge.
- Final closure of blocking findings.
### 9.7 Repository and CI backstop

All changes entering protected branches should pass a Holodeck status check independent of the coding tool used.

```text
Required repository checks
  - valid Holodeck task and candidate revision
  - accepted context and completion record
  - requirement coverage gate
  - review findings gate
  - independent verification gate
  - policy/approval gate
  - no unresolved critical risk
```

### 9.8 Bypass and trace limitations

- Holodeck cannot guarantee documentation for actions performed entirely outside its control.
- Imported work MUST display a reduced-observability flag and require stronger review/verification.
- The system MUST distinguish “no event occurred” from “the adapter could not observe the event.”
- Humans with repository authority can bypass local adapters, so protected-branch and release gates are essential.
### 9.9 Acceptance criteria

- An agent process ending successfully never directly marks a task completed.
- A run without a valid completion or interruption record cannot be accepted.
- Claims in the completion candidate are mechanically compared with observed trace data.
- The same server-side protocol supports multiple agent tools through adapters.
- Protected repository changes can be blocked when Holodeck records are missing or insufficient.
