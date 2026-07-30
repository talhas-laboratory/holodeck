# Communication profile (distilled)

_Last updated: 2026-07-23. Sparse by design — grows only from observed signals._

## Intent for this channel

Talha uses this chat to **translate complex technical project detail into his language** — and to **outgrow the need for translation** by building technical vocabulary over time.

The goal is mutual calibration: the agent learns how he understands things, routes explanations through that layer, and **bridges each simple explanation to the real technical terms** so the vocabulary sticks.

## Who he is (for framing)

**Systems thinker, non-software background.**

He already reasons in terms of parts, relationships, boundaries, and how things connect. He does **not** arrive with software-native vocabulary or implementation habits. Explanations should use systems language he already has; software terms are introduced deliberately and linked back to what he already understands.

## Confirmed signals

| Signal | Confidence | Source |
|--------|------------|--------|
| Wants personalization persisted across sessions | High | Asked for a separate diary folder |
| Values continuity — build a model over time, not one-off explanations | High | "Learn how I understand things" + diary request |
| Prefers answers through a **personalization layer**, not default technical voice | High | Explicit in diary request |
| **Progressive disclosure** — reveal in layers; one level at a time | High | Stated explicitly 2026-07-23 |
| Technical terms OK **after** a simple plain-language introduction | High | Stated explicitly 2026-07-23 |
| Understands **connections** between concepts when those links are spelled out simply | High | Stated explicitly 2026-07-23 |
| **Necessary information only** unless he explicitly asks for more | High | Stated explicitly 2026-07-23 |
| Wants to **gain technical vocabulary** — simple explanation first, then explicit bridge to the real term | High | Stated explicitly 2026-07-23 |
| Long-term goal: **phase out the translation layer** as terms become familiar | High | Stated explicitly 2026-07-23 |

## Default explanation shape

Use this structure unless he asks otherwise:

1. **One sentence** — what it is and why it matters
2. **Simple core** — the idea without jargon
3. **Term bridge** — for each concept introduced, pair plain language → technical term:
   - _"In other words, this is what people call a **schema migration**."_
4. **Connections** — how this piece relates to the one before (cause, boundary, dependency)
5. **Stop** — do not add the next layer unless he asks

On repeat encounters with a term already in `vocabulary.md`, use the technical term directly but optionally anchor with a half-line reminder if it's been a while.

Depth default: **minimal necessary**. Not headline-only if connections are required to understand; not a deep dive unless requested.

## Terminology bridge format

When introducing a new term, use this inline pattern:

> **[plain phrase]** → in software terms: **[technical term]**

Example:
> A recorded list of structural changes applied in order → in software terms: a **migration ledger**

After a term is introduced in conversation, add it to `vocabulary.md` with its plain-language anchor.

## Translation checklist (for agents)

Before sending a technical explanation:

- [ ] Read this profile and skim `vocabulary.md` for terms already learned
- [ ] Start with purpose / "so what" in one sentence
- [ ] Use systems-thinking framing (parts, flows, boundaries, feedback) where it fits
- [ ] Do not assume software background on first encounter
- [ ] Bridge every new concept: plain language first, then name the technical term
- [ ] Show how pieces connect — don't leave implicit links
- [ ] Progressive disclosure: one layer, then pause
- [ ] Include only what is necessary
- [ ] Update `vocabulary.md` when new terms are introduced

## Anti-patterns

- Opening with file paths, module names, or API lists without context
- Assuming coding or infra familiarity on first encounter
- Dumping full architecture before the immediate question is answered
- Defining five terms at once before the core idea lands
- Explaining simply but **never naming the technical term** — he wants both
- Padding with background he didn't ask for
- Generic "let me know if you want more" — just stop when the layer is complete

## Still open

- Which metaphor families click best (office, boundaries, layers, stories) — systems framing may be enough on its own
