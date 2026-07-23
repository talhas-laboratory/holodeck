# Holodeck agent direction

## Design principles

- Anything we build must be thought through elegantly. Prefer the most elegant solution to the problem at the current stage — not the most elaborate, and not a premature abstraction for a later stage we have not reached.
- Build with modularity in mind so we can iterate and change infrastructure quickly. Keep domain logic, storage, HTTP/CLI adapters, and future agent adapters separable. Prefer small, replaceable boundaries over tangled one-off designs.

## How to apply this

- Solve the problem in front of you with the simplest correct shape that preserves a clean seam for change.
- Do not rewrite infrastructure for taste alone; do design so a swap (store, HTTP layer, packaging, adapters) stays localized.
- Favor explicit modules, domain errors, and thin adapters over framework weight or speculative generality.
