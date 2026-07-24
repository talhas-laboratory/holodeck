# Agent Rules

Project-wide direction lives in the repo root [`AGENTS.md`](../../../AGENTS.md): elegant solutions at every stage, and modularity so infrastructure can change quickly.

Board-specific:

- Prefer sparse, high-signal updates over verbose status narratives.
- Keep task packets self-contained enough for another agent to resume.
- Update board state as part of the work, not after memory fades.
- Use append-only updates for activity history; edit task files for current state.
- Preserve provenance for imported context and sidecar work.
- Do not mark work done without test or verification evidence.
- Escalate blockers early with the smallest concrete question.
