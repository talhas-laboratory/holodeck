# M1 agent rules

- Read the M1 design before making a kernel, schema, lifecycle, policy, or adapter decision.
- Keep external provider, model, repository, and agent-runtime types out of domain logic.
- Preserve exact revision, tenant, actor, authority, and provenance references.
- Never mark policy or tooling as enforced without a tested mediation point.
- Record a durable decision before relying on a cross-cutting architectural choice.
- Prefer one task packet per independently verifiable change.
