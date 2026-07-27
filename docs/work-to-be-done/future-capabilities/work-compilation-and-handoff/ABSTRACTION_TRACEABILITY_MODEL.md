# Abstraction and traceability model

Work should move through explicit levels without severing links to the level
that gives it meaning:

```text
product direction
→ workspace purpose and policy
→ mission outcome
→ requirements and constraints
→ capabilities and workstreams
→ atomic tasks
→ role-specific execution instructions
→ evidence and semantic handoff
```

Each lower-level record references the exact revisions from which it was
derived. A task package must therefore answer both directions:

```text
Why does this task exist?
What higher-level outcome does it serve?

What must this role do now?
Which constraints and evidence obligations apply?
```

## Context selection rule

The package may omit material from its delivery payload, but cannot erase it
from the trace. Every source is one of:

- included and binding;
- included as authoritative reference;
- included as untrusted or generated context;
- omitted with a recorded reason and retrieval reference; or
- excluded because it is irrelevant or not permitted.

Critical requirements and binding instructions cannot be omitted solely for a
token budget. Generated summaries do not replace source records.

## Required links

| From | To | Why |
| --- | --- | --- |
| Task | Requirement / mission revision | Explains intended outcome. |
| Task | Decision register | Identifies fixed choices and prohibited alternatives. |
| Task | Ambiguity register | Makes uncertainty visible and governs escalation. |
| Task | Dependencies | Makes prerequisite outputs and ordering explicit. |
| Task | Acceptance scenarios | Provides the observable correctness oracle. |
| Handoff packet | Task and role revision | Bounds work and authority. |
| Handoff packet | Context bundle and omissions | Makes selection inspectable and expandable. |
| Evidence / completion handoff | Task, mission, and package revision | Tests semantic continuity. |
