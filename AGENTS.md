# Holodeck agent direction

## Required product context

Before making a product, architecture, integration, or execution-model decision, read:

1. `docs/product-vision/README.md`
2. `docs/product-vision/PRODUCT_VISION.md`
3. `docs/product-vision/DECISION_GUIDE.md`

When the work touches human/agent collaboration platforms, external event
ingress, agent launching, project or repository bindings, or signed approvals,
also read `docs/product-vision/BUZZ_INTEGRATION_STRATEGY.md`.

Treat the product vision as durable direction, not as proof that a capability
already exists. Verify current behavior in source and tests. If an implementation
choice conflicts with the product vision, record the conflict and rationale
before proceeding.

## Design principles

- Anything we build must be thought through elegantly. Prefer the most elegant solution to the problem at the current stage — not the most elaborate, and not a premature abstraction for a later stage we have not reached.
- Build with modularity in mind so we can iterate and change infrastructure quickly. Keep domain logic, storage, HTTP/CLI adapters, and future agent adapters separable. Prefer small, replaceable boundaries over tangled one-off designs.

## How to apply this

- Solve the problem in front of you with the simplest correct shape that preserves a clean seam for change.
- Do not rewrite infrastructure for taste alone; do design so a swap (store, HTTP layer, packaging, adapters) stays localized.
- Favor explicit modules, domain errors, and thin adapters over framework weight or speculative generality.
