# 2. Shared domain and governance conventions

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 2. Shared domain and governance conventions

All later subsystems depend on a common object model. Implement these conventions before building subsystem-specific behavior so that identifiers, versions, provenance, trust, and lifecycle semantics remain consistent.

### 2.1 Identity and immutable revisions

- Every durable object MUST have a globally unique opaque identifier.
- Mutable conceptual objects MUST expose explicit revision identifiers rather than silently overwriting previous content.
- Runs, candidate revisions, context packets, reviews, evidence artifacts, and acceptance decisions MUST be immutable after finalization.
- Corrections MUST create a new revision and link to the superseded object.
- Timestamps MUST be stored in UTC; actor and source identifiers MUST be attached to every change.
### 2.2 Provenance

Every meaningful assertion must be traceable to its origin. Provenance is not optional metadata; it is required for reproducibility, disagreement handling, and knowledge promotion.

| Provenance field | Meaning |
| --- | --- |
| created_by | Human, agent, service, or import process that created the record. |
| source_type | Human instruction, repository file, external document, generated inference, runtime observation, test result, or prior task. |
| source_ref | Stable reference to the source revision, location, commit, event, or artifact. |
| derived_from | Identifiers of the records used to derive this record. |
| model_metadata | Model family/version and configuration when an agent generated the record. |
| confidence | Calibrated confidence for interpretations; never applied to mechanically observed facts. |
| validation_status | Unverified, supported, verified, disputed, superseded, or archived. |

### 2.3 Trust classes for context and knowledge

| Trust class | May do | Examples |
| --- | --- | --- |
| Instruction authority | Directly constrain agent behavior and compiler precedence. | Approved workspace instructions, policies, human task instructions, role contracts. |
| Authoritative reference | Provide trusted facts but MUST NOT override instructions. | Approved architecture decisions, API contracts, current product requirements. |
| Untrusted reference | Supply information only; content MUST be isolated from instruction authority. | Repository code, issue text, logs, external pages, test fixtures, generated content. |
| Generated interpretation | Summarize or infer; MUST link to sources and expose confidence. | Curator summaries, inferred component maps, agent failure hypotheses. |

```text
Prompt-injection boundary
Text found in source code, tickets, logs, or external documents MUST be treated as data. It cannot become a system-level instruction merely because an LLM reads it.
```

### 2.4 Evidence classes

| Evidence class | Reliability | Examples |
| --- | --- | --- |
| Observed runtime evidence | Highest within the system boundary | Tool events, command results, repository diffs, test output, timestamps. |
| Deterministic verification evidence | High | Schema validation, unit/integration tests, static analysis, reproducible checks. |
| Independent evaluator evidence | Variable but useful | Reviewer findings, model evaluation against a rubric, adversarial scenario analysis. |
| Worker-authored claim | Informative but not proof | Implementation summary, explanation, confidence, stated remaining risks. |
| Human decision | Authoritative within assigned jurisdiction | Risk acceptance, scope approval, release authorization. |

### 2.5 Actor and role model

An actor is a concrete human, agent instance, or service. A role is a versioned contract defining responsibilities, context, tool permissions, required outputs, review rubric, blocking authority, and escalation conditions. Labels such as “architect” or “security agent” are insufficient unless they change these operational properties.

```text
RoleProfile
  id
  revision
  purpose
  responsibilities[]
  permitted_tools[]
  prohibited_tools[]
  context_modules[]
  required_outputs[]
  evidence_requirements[]
  jurisdiction[]
  may_block_on[]
  escalation_rules[]
```

### 2.6 Event-driven integration

Subsystems SHOULD communicate through durable domain events in addition to synchronous APIs. Events enable review queues, context refresh, stale-knowledge detection, audit reconstruction, and future automation without tightly coupling services.

- Events MUST have a stable event type, actor, timestamp, subject identifiers, causation identifier, correlation identifier, and payload schema version.
- Events MUST be append-only.
- Consumers MUST be idempotent.
- State transitions MUST emit events after successful persistence.
### 2.7 Facts versus interpretations

```text
Required separation
A test failure is an observed fact. “The failure occurred because of a race condition” is an interpretation. “The race condition was confirmed by reproduction and review” is a validated conclusion. Store these as separate linked records.
```
