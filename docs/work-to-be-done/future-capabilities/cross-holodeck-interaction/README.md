# Cross-Holodeck interaction

**Status:** Design seed / thing to ponder; not current runtime behavior, not a
build-milestone commitment.

Holodeck instances today are local authorities. Connecting different Holodecks
together is a recurring product idea. Before choosing a protocol, topology, or
shared store, the underlying problem and the value of combining instances need
to be reasoned through.

This package parks that inquiry so later design can start from purpose rather
than from a networking shape.

## Intent

Enable cross-Holodeck interaction: connect distinct Holodeck instances so they
can cooperate when that cooperation produces real product value.

## Reasoning order

Work through these questions in order. Do not skip ahead to transport, sync, or
federation mechanics until earlier answers are clear enough to constrain them.

### 1. What underlying problems is Holodeck trying to solve?

Start from product vision and the current local authority model. Name the jobs
a single Holodeck already owns (or is intended to own):

- turning human intent into governed, inspectable work;
- bounding authority, scope, claims, and acceptance;
- keeping durable records of origin, mission, evidence, and decisions;
- coordinating agents inside one semantic / execution workspace.

Ask which of those jobs are inherently single-instance, and which only look
local because the alpha is local-first.

Related sources: `docs/product-vision/`, `docs/architecture.md`, and the
explicit deferrals around remote multi-agent networking and hosted multi-tenant
control planes.

### 2. What could combining two Holodecks enable?

Only after (1), reason over the benefits that *require* more than one Holodeck
authority rather than a larger workspace, another adapter, or a shared Git/CI
surface. Candidate benefit classes to evaluate (accept, reject, or reframe):

- spanning separately governed projects or organizations without collapsing
  their authority;
- handing off a completed mission, evidence packet, or review obligation to
  another Holodeck that owns the next bounded domain;
- coordinating agents that must not share one SQLite / policy / claim domain;
- mirroring or following work across environments (e.g. personal vs team,
  local vs remote) while preserving each instance as an authority;
- composing specialized Holodecks (research, implementation, verification)
  without creating one opaque mega-kernel.

For each plausible benefit, state what remains authoritative in each Holodeck
and what crosses the boundary as a reference, packet, or request.

### 3. What would need to happen to connect them for those benefits?

Only after (2), reason over the minimum seams required to achieve the retained
benefits. Prefer questions over premature answers:

- What objects may cross a boundary (origin references, mission packets,
  evidence, claims, actor mappings, status), and which must never leave their
  home authority?
- Is the relationship peer federation, directed handoff, client/server, or
  temporary bridging?
- How are identity, trust, and policy expressed across instances without
  collapsing tenants or inventing a new universal source of truth?
- What failure, replay, and idempotency properties are required so reconnects
  and duplicates do not fork governance state?
- What can stay adapter-shaped so Holodeck's domain logic remains local and
  replaceable?

Any concrete design that follows should preserve the enduring principle that
objects crossing a boundary carry stable references in both directions, and
that collaboration / Holodeck / Git-CI authorities stay partitioned.

## Explicit non-goals for this seed

- Choosing a wire protocol, sync engine, or shared database.
- Treating “connect Holodecks” as itself a milestone outcome.
- Replacing the local-first alpha model before the governed vertical slice is
  proven.
- Collapsing multiple Holodecks into one hosted multi-tenant control plane by
  default; that remains a separate, deferred product question.

## When to promote this

Promote out of “things to ponder” only when:

1. the underlying single-Holodeck jobs are crisp enough to say what must stay
   local;
2. at least one cross-instance benefit is clearly not solvable by workspace,
   adapter, or Git/CI boundaries alone; and
3. the connection seam can be described as a small, replaceable boundary with
   explicit authority ownership.

At that point, turn this seed into a capability specification and, if
warranted, a build-milestone proposal. Until then, keep implementation out of
active taskboards.
