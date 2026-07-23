# Gates

Every task must pass these gates before it is treated as complete.

## Intake Gate

- Problem is stated in one sentence.
- Scope-in and scope-out are explicit.
- Owner or active agent is named.
- Dependencies and unknowns are listed.

## Readiness Gate

- Relevant repo files or docs are linked.
- Test strategy is named before implementation.
- Failure mode is described.
- Acceptance criteria are concrete and inspectable.

## Implementation Gate

- Changes are scoped to declared files.
- New abstractions are justified by repeated complexity or a local pattern.
- User or unrelated worktree changes are preserved.
- Updates are recorded in `UPDATES.jsonl`.

## Verification Gate

- Commands run are listed exactly.
- Results are recorded, including failures.
- Manual checks include artifact paths or screenshots when relevant.
- Known residual risks are stated.
- Every acceptance criterion has direct evidence; a happy-path smoke test is not evidence for a broader invariant.
- When state crosses a boundary (database, API, CLI, adapter, package, or container), verification checks the same result on both sides.
- Verification-created containers, volumes, files, and temporary state are cleaned up or recorded explicitly.

## Review Gate

- Another agent or reviewer can understand the task from the task packet alone.
- Decision log is updated for architectural choices.
- Handoff notes describe what changed and what remains.

## Done Gate

- Acceptance criteria are satisfied.
- Verification evidence is attached.
- Task file, `TASKS.md`, and lane placement agree.
- No hidden follow-up is required for the stated scope.
- A residual risk must not contradict an acceptance criterion or the track's stated product guarantee; if it does, the task remains in review or is split.
- Any external publication, archival, deletion, or credentialed release has explicit owner approval and recorded external-state evidence.
