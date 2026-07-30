# 3. Persistent workspace intelligence

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 3. Persistent workspace intelligence

A workspace must become a durable model of the project rather than a folder with a short goal statement. This model is the upstream source for requirements, context routing, reviewer alignment, and future learning.

```text
Decision
The workspace curator builds a persistent context architecture at onboarding and refresh. It does not merely generate a one-time system prompt.
```

### 3.0.1 Persistent factual repository representation

For each active repository binding, workspace intelligence may maintain an
immutable factual graph scoped to one exact repository revision. Its purpose is
to preserve mechanically evidenced entities and relations for later bounded
retrieval; it is not a permanent semantic interpretation of the codebase.

The initial factual profile includes files, modules, classes, functions,
methods, tests, manifests, configuration, migrations, schemas, API entry
points, and evidence-backed relations such as containment, definitions,
imports, calls, inheritance, reads/writes, tests, configuration, and
migrations.

Every fact must expose:

- tenant, workspace, repository binding, and immutable repository revision;
- exact source and source-observation identity;
- repository-relative location and source span where applicable;
- extractor identity, version, schema, configuration, and observation method;
- explicit coverage limitations and diagnostics.

Extractor output is untrusted observation data and is normalized through a
provider-neutral adapter. Provider schemas and graph databases do not become
the Holodeck domain model. Failed or partial extraction cannot silently replace
the active complete snapshot. Prior snapshots remain queryable.

Bounded queries must specify entity/relation kinds, direction, depth, result
limits, and visited-node limits, and must return provenance, coverage,
truncation, and omission reasons. Failure to find a relation does not establish
that no dependency or risk exists.

Component purpose, lifecycle status, product/security meaning, task relevance,
and cross-dimensional implications are not facts in this graph. M3 may propose
them as task-local, evidence-linked hypotheses.

### 3.1 Workspace model

| Area | Required content |
| --- | --- |
| Identity and purpose | What the project is, why it exists, intended outcomes, current maturity, and explicit non-goals. |
| Users and stakeholders | Human roles, system actors, agent roles, goals, authority, workflows, likely mistakes, and failure consequences. |
| Product model | Capabilities, features, user journeys, service promises, trade-offs, and risk tolerance. |
| Architecture map | Components, responsibilities, interfaces, dependencies, data stores, external systems, and boundaries. |
| Principles and constraints | Approved engineering principles, compatibility constraints, security posture, dependency policy, operational expectations. |
| Domain language | Canonical terms, aliases, definitions, and prohibited ambiguous terms. |
| Knowledge sources | Registered source locations, ownership, trust class, revision, freshness, and relevant modules. |
| Decisions and gaps | Accepted decisions, rejected alternatives, unresolved questions, contradictions, and missing documentation. |

### 3.2 Source registry

All workspace knowledge must originate from a registered source or an explicitly generated interpretation. The source registry enables provenance, freshness, trust classification, and targeted refresh.

```text
WorkspaceSource
  id
  workspace_id
  source_type             # repository_file, document, API, human_input, task_history
  locator
  revision                # commit, file hash, document revision, or external version
  trust_class
  owner
  sensitivity
  refresh_policy
  last_observed_at
  stale_status
  module_tags[]
  instruction_authority   # true only for explicitly approved instruction sources
```

### 3.3 Context modules

Do not create one growing workspace prompt. Divide knowledge into reusable, versioned context modules. A module combines a bounded purpose, approved instructions, references, applicability rules, and freshness metadata.

| Example module | Purpose |
| --- | --- |
| core-principles | Stable project-wide principles and non-negotiable constraints. |
| product-and-users | Product purpose, stakeholder roles, user scenarios, and failure consequences. |
| architecture | System components, boundaries, dependencies, and cross-cutting invariants. |
| data-and-persistence | Data model, lifecycle, migrations, retention, and integrity expectations. |
| testing-and-verification | Test conventions, required test layers, evidence policies, and tooling. |
| security-and-authority | Trust boundaries, permissions, protected assets, and escalation requirements. |
| operations-and-release | Deployment, monitoring, rollback, support, and incident expectations. |

### 3.4 Generated summaries are not authority

- A curator-generated summary MUST identify itself as generated interpretation.
- It MUST link to exact source revisions and relevant sections.
- The original source MUST remain retrievable.
- Critical constraints SHOULD be supplied to workers as approved original text or formally normalized requirements, not only as summaries.
- Conflicting sources MUST remain explicit; the curator must not silently collapse disagreement into one answer.
### 3.5 Freshness and refresh

Workspace intelligence cannot be frozen at onboarding. Refresh must be selective and event-driven.

| Trigger | Expected behavior |
| --- | --- |
| Registered source revision changes | Mark dependent modules stale and enqueue targeted refresh. |
| Architecture or policy document changes | Require re-evaluation of affected modules and tasks. |
| Task touches an unknown component | Create a knowledge-gap record and invoke targeted curation. |
| Repeated failure pattern appears | Propose a new or updated requirement, test strategy, or knowledge module. |
| Human changes workspace purpose or risk posture | Create a new workspace-model revision and identify affected active tasks. |
| Worker requests missing context | Route to on-demand curation without modifying the active packet silently. |

### 3.6 Human review and approval

- The curator MAY auto-approve low-risk descriptive metadata.
- New instruction-authority content MUST require approval unless created directly by an authorized human.
- Changes to project purpose, non-goals, risk posture, or binding principles MUST create an approval request.
- The user interface MUST show source, confidence, proposed status, and affected modules for each curator output.
### 3.7 Minimum APIs

```text
POST /workspaces/{id}/intelligence/onboard
POST /workspaces/{id}/intelligence/refresh
GET  /workspaces/{id}/model?revision=...
GET  /workspaces/{id}/sources
POST /workspaces/{id}/sources
GET  /workspaces/{id}/context-modules
POST /workspaces/{id}/context-modules/{module}/approve
GET  /workspaces/{id}/knowledge-gaps
POST /workspaces/{id}/knowledge-gaps/{gap}/resolve
```

### 3.8 Acceptance criteria

- A newly onboarded workspace produces a versioned workspace model, source registry, context modules, open questions, and provenance report.
- No generated summary can be mistaken for approved instruction authority.
- Changing a registered source marks only dependent modules stale.
- A user can inspect what Holodeck believes the project is, why it believes it, and which parts remain uncertain.
- Old workspace-model revisions remain available for reproducing previous runs.
