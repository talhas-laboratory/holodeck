# M1 case study: from direction to fresh-builder handoff

M1 supplied the first manual reference workflow.

```text
human/product aspiration
→ governed execution-kernel direction
→ M1 authority-substrate boundary
→ locked architecture decisions
→ canonical records and invariants
→ governance scenarios
→ dependency-ordered task packets
→ fresh-builder audit
→ missing-ownership repair
→ implementation handoff
```

The original taskboard was detailed but incomplete: records and seams used by
later tasks did not always have explicit owners. The fresh-builder audit found
that gap by asking whether an agent with only the repository could implement
every required concept without inventing architecture. The repair added explicit
record-family, repository/unit-of-work, catalog, and baseline packets.

## Reusable lessons

- Start from durable product invariants, not a desired table or API list.
- Keep distinctions such as source versus interpretation, approval versus
  message, mission versus run, and evidence versus claim explicit.
- Close foundational decisions before delegating implementation detail.
- Give every durable concept, dependency, and test oracle a named owner.
- Test negative effects: a denied command must also omit forbidden state,
  events, and delivery effects.
- Treat a fresh-agent simulation as a way to expose hidden context and missing
  ownership.
- Keep gate scope explicit. The fresh-builder audit established whether an
  agent could start reliable implementation; it did not establish that a later
  implementation was correct, accepted, or operationally ready.

## Gate-scope correction

During the M1 discussion, a handoff-readiness question was initially evaluated
using implementation-certification concerns such as independent review, clean
candidate evidence, supported-version matrices, migration recovery, and
operational readiness. Those concerns were useful, but they answered a
different question.

The correction produced a reusable rule:

> A readiness gate says whether bounded work may begin. An acceptance gate says
> whether a result may be trusted as complete. Evidence for one must not be
> silently used as evidence for the other.

The broader certification concerns are retained in [Gate taxonomy](GATE_TAXONOMY.md)
for M4–M8 rather than being imposed on every early planning handoff.

The M1 materials are reference evidence, not a universal template. Future work
must retain the method while adapting its vocabulary and risk requirements.
