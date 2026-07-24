# Agent adapters and enforceable completion

## Purpose

Enforce the accepted workflow through runtime-owned transitions and evidence, not prompt instructions alone.

## Generic adapter

The adapter reports capabilities; prepares environments; configures permissions; launches agents; streams events; requests permissions/checkpoints/completion candidates; captures repository state; terminates runs; collects final state; and normalizes results.

## Launcher and completion protocol

Create isolated execution space, record start revision/environment, compile and store the packet, configure tools/budgets/output schema, launch where possible, collect trace/worklog, then require a completion or interruption record. The server validates schema, trace consistency, requirement/evidence coverage, freezes a candidate revision, creates review, verifies independently, and uses gates for acceptance.

## Backstop and limitations

Protect merge/release with a Holodeck status check independent of the agent. Imported external work is reduced-observability and receives stronger review/verification. Never confuse an unobserved event with a proven absence. Humans can bypass local adapters, so repository protections remain essential.
