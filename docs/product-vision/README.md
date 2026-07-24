# Holodeck product vision

This folder contains the durable product direction agents must use when making
product and architecture decisions.

Holodeck is intended to become the governed execution kernel behind
human-and-agent collaboration platforms. A human should be able to express work
in a platform such as Buzz; Holodeck should turn that request into an
inspectable mission, create an appropriate execution workspace, coordinate
agents, collect evidence, and return progress and results to the originating
conversation.

## Reading order

1. [Product vision](PRODUCT_VISION.md) — the north star, product boundary, and
   enduring principles.
2. [Decision guide](DECISION_GUIDE.md) — the checks agents must apply before
   choosing an implementation shape.
3. [Buzz integration strategy](BUZZ_INTEGRATION_STRATEGY.md) — the researched
   reference architecture, current compatibility, gaps, and phased path.

## Authority and freshness

- `PRODUCT_VISION.md` and `DECISION_GUIDE.md` are durable directional context.
- `BUZZ_INTEGRATION_STRATEGY.md` is a dated architecture assessment. Its
  principles are durable, but claims about Buzz's implementation must be
  revalidated against the upstream repository before integration work.
- `docs/work-to-be-done/` contains specifications, proposals, and historical
  implementation evidence. Those documents explain what may be built and what
  has been done; this folder explains what the product is trying to become.
- Source code and tests remain authoritative for what Holodeck currently does.

Explicit current user instructions take precedence. When a proposed change
conflicts with this vision, agents must make the conflict visible and record the
reason for the exception rather than silently changing the product direction.

## Core decision

Collaboration systems and Holodeck have different jobs:

- The collaboration system owns human interaction, identity, conversation, and
  signed external events.
- Holodeck owns semantic workspaces, missions, execution authority, evidence,
  and acceptance.
- Repositories and CI own code revisions, executable artifacts, test results,
  and merge enforcement.

Integration should connect these authorities through replaceable adapters. It
must not collapse them into one ambiguous source of truth.
