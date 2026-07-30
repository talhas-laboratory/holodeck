# Gates

## Intake

- The packet links the relevant design section and source files.
- Scope and explicit non-goals are recorded.
- Dependencies, migration effects, and open questions are identified.

## Readiness

- The public/domain contract is written before code.
- Required invariants and failure modes are named.
- Unit, migration, concurrency, and integration test strategy is stated as applicable.

## Implementation

- Domain logic remains independent of HTTP, MCP, database, agent, and platform SDK types.
- Storage constraints back critical invariants where SQLite can enforce them.
- Existing user changes and legacy behavior are preserved unless the task says otherwise.

## Verification

- Exact commands and results are recorded in the task packet.
- Positive, negative, idempotency/retry, and migration paths are tested where relevant.
- A cross-boundary test verifies externally visible API behavior against persisted state.
- Residual risks are explicit; advisory controls are never called enforced.

## Done

- Acceptance criteria have direct evidence.
- Packet, task index, lane placement, and update history agree.
- No hidden M2–M8 capability has been smuggled into the task.
