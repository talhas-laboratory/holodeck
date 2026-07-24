# Holodeck Product Architecture and Implementation Blueprint

**Status:** Product architecture and implementation specification  
**Purpose:** Convert the agreed product ideas into an actionable development plan that a coding agent or engineering team can use to scope, design, and implement Holodeck.  
**Scope:** This document captures the decisions and ideas developed in the branch of discussion beginning with the evaluation of Holodeck as a dark-software-factory runtime. It intentionally excludes unrelated earlier conversation history.

---

# 1. Executive Summary

Holodeck should not be built primarily as a generic multi-agent orchestrator or prompt manager.

It should be built as a **governed compiler and runtime for autonomous software work**.

Its job is to transform:

- human intent,
- project and workspace knowledge,
- technical reality,
- policies,
- uncertainty,
- delegated authority,
- quality expectations,
- risks,
- and available verification capabilities

into a bounded, versioned, inspectable **Mission** that agents can execute and independent systems can verify.

The core flow is:

```text
User Intent
    ↓
Workspace Genesis
    ↓
Persistent Workspace Context Library
    ↓
Task Intent
    ↓
Delegation Contract
    ↓
Mission Compiler
    ↓
Scope + Context + Requirements + Tests + Environment + Roles
    ↓
Definition Gate
    ↓
Execution Gate
    ↓
Controlled Agent Execution
    ↓
Independent Verification
    ↓
Semantic Handoff Check
    ↓
Accept / Reject / Escalate
    ↓
Workspace Learning
```

The product should make one central guarantee:

> Every autonomous decision must be traceable to explicit user intent, approved workspace principles, delegated implementation discretion, or clearly labelled inference. Uncertainty that could materially change the outcome must cause narrowing, escalation, or refusal—not silent interpretation.

Holodeck should aim for strong autonomy over **execution decisions**, selective autonomy over **optimization decisions**, caution over **interpretation decisions**, and no silent autonomy over **intent decisions**.

---

# 2. Product Thesis

## 2.1 Problem

Modern coding agents can generate code quickly, but autonomous software production remains unreliable because agents often lack:

- sufficient project meaning,
- stable workspace knowledge,
- clear authority boundaries,
- precise requirements,
- reliable test oracles,
- reproducible environments,
- independent verification,
- and a way to preserve user intent across delegation.

Existing tools often optimize the worker agent while neglecting the surrounding system that determines:

- what the worker should know,
- what it is allowed to decide,
- what must become true,
- how success is measured,
- and why the result should be trusted.

## 2.2 Product thesis

Holodeck is a system for compiling software work into inspectable, governed missions.

It should:

1. Build a persistent model of each workspace.
2. Distinguish human intent from current technical reality.
3. Compile new tasks into bounded missions.
4. Provide each agent only the context appropriate to its role.
5. Create or select the correct execution and test environment.
6. Generate requirements from purpose, users, risk, and system reality.
7. Generate test strategies from requirements, failure models, and observable boundaries.
8. Enforce decision rights, permissions, and state transitions.
9. Require evidence before accepting work.
10. Check both technical correctness and semantic fidelity.
11. Learn from failures, corrections, and completed missions.

## 2.3 Non-goals

Holodeck should not initially attempt to:

- become a universal autonomous product manager,
- infer a user’s values without explicit evidence,
- replace human authority over high-consequence product or policy decisions,
- ingest every document into every agent prompt,
- use one opaque LLM to define intent, implement work, and judge success,
- guarantee perfect understanding of ambiguous human intent,
- treat passing tests as proof of complete correctness,
- or become a fully dark software factory across all work types from day one.

The realistic target is:

> Highly reliable, inspectable autonomy for bounded and sufficiently verifiable work.

---

# 3. Core Architectural Principles

## 3.1 Agents provide judgment; the kernel provides authority

LLM-based agents may propose:

- workspace interpretations,
- context selection,
- requirements,
- risks,
- tests,
- environment plans,
- implementation approaches,
- and verification findings.

The deterministic runtime must control:

- state transitions,
- versioning,
- permissions,
- source trust levels,
- approval rules,
- context budgets,
- claim acquisition,
- evidence requirements,
- acceptance gates,
- and audit logs.

## 3.2 Context must be compiled, not dumped

Agents should not receive the full workspace by default.

Context should be:

- role-specific,
- task-specific,
- risk-aware,
- versioned,
- traceable,
- limited,
- progressively expandable,
- and separated by authority level.

The objective is **minimum sufficient context**, not minimum context and not maximum context.

## 3.3 Intent, facts, policy, and inference must remain separate

Holodeck must distinguish:

- **Intentional truth:** what humans want.
- **Descriptive truth:** what the system currently is.
- **Normative truth:** what is required or allowed.
- **Inference:** what the compiler derives.
- **Assumption:** what is currently believed without sufficient evidence.
- **Decision:** what was chosen under delegated authority.
- **Observation:** what actually happened at runtime.

These must never be flattened into one undifferentiated prompt or knowledge store.

## 3.4 Requirements are compiled from meaning

Requirements should be derived through:

```text
Purpose
→ Stakeholders
→ Scenarios
→ Risks
→ System Model
→ Constraints
→ Requirements
```

They should not be inferred from implementation alone.

## 3.5 Tests are compiled from requirements and failure hypotheses

Tests should be derived through:

```text
Requirement
→ Failure Model
→ System Boundary
→ Oracle
→ Environment
→ Test Strategy
→ Executable Tests
```

The implementation agent must not control all acceptance evidence.

## 3.6 Completion is not self-declared

A worker may submit a completion candidate.

Only the verification and gate system may mark a mission as verified or accepted.

## 3.7 Autonomy must be risk-adjusted

Autonomy should depend on:

- consequence of failure,
- reversibility,
- clarity of intent,
- scope confidence,
- testability,
- security sensitivity,
- data sensitivity,
- novelty,
- and operational impact.

## 3.8 Uncertainty must be represented explicitly

Every important context item should have:

- source,
- authority,
- freshness,
- confidence,
- epistemic type,
- version,
- conflicts,
- and applicability.

Unknown is a valid state. Fabricated certainty is not.

---

# 4. Core Product Objects

The initial domain model should include the following first-class objects.

## 4.1 Workspace

A persistent governed representation of a project or system.

A Workspace contains:

- identity,
- purpose,
- users,
- capabilities,
- technical system model,
- policies,
- context modules,
- source registry,
- agent roles,
- readiness state,
- and epistemic state.

## 4.2 Context Item

A typed unit of knowledge, instruction, observation, or inference.

Recommended fields:

```yaml
context_item:
  id:
  workspace_id:
  type:
  statement:
  source_refs:
  authority:
  confidence:
  freshness:
  version:
  status:
  applies_to:
  conflicts_with:
  created_by:
  approved_by:
  created_at:
  updated_at:
```

Recommended types:

- source_fact
- approved_instruction
- workspace_rule
- retrieved_reference
- generated_summary
- task_interpretation
- derived_implication
- assumption
- open_question
- conflict
- decision
- runtime_observation
- incident_learning

## 4.3 Context Module

A reusable collection of context items for a coherent concern.

Examples:

- core-principles
- product-purpose
- user-model
- domain-model
- database-architecture
- security-boundaries
- migration-policy
- testing-policy
- deployment-policy
- observability
- accessibility
- historical-incidents

## 4.4 Source

A registered origin of knowledge.

Examples:

- repository file,
- documentation section,
- issue,
- architecture decision,
- policy document,
- human statement,
- runtime trace,
- test result,
- external standard,
- generated summary.

Recommended source trust classes:

1. **Instruction authority**
2. **Authoritative reference**
3. **Trusted observation**
4. **Ordinary reference**
5. **Untrusted external content**
6. **Generated interpretation**

## 4.5 Agent Profile

A functional role definition, not a personality.

Recommended fields:

```yaml
agent_profile:
  id:
  workspace_id:
  role:
  responsibilities:
  system_instructions:
  allowed_tools:
  forbidden_tools:
  default_context_modules:
  required_outputs:
  completion_contract:
  escalation_conditions:
  risk_ceiling:
  version:
```

Examples:

- workspace-curator
- task-requirement-engineer
- scope-analyst
- test-strategist
- implementation-worker
- security-reviewer
- migration-specialist
- independent-test-generator
- verifier
- intent-verifier
- release-reviewer

## 4.6 Task

A user or system request before complete compilation.

A task is an expression of desired work, not yet a fully executable mission.

## 4.7 Delegation Contract

A versioned semantic contract that defines what Holodeck is authorized to decide.

Recommended fields:

```yaml
delegation_contract:
  id:
  task_id:
  expressed_request:
  intended_outcome:
  user_value:
  required_properties:
  acceptable_variation:
  forbidden_outcomes:
  non_goals:
  preference_order:
  delegated_decisions:
  escalation_decisions:
  assumptions:
  unresolved_questions:
  approval_status:
  version:
```

## 4.8 Requirement

A structured statement of what must become or remain true.

Recommended fields:

```yaml
requirement:
  id:
  mission_id:
  statement:
  rationale:
  source_goal:
  affected_stakeholders:
  type:
  priority:
  invariant:
  preconditions:
  expected_behavior:
  forbidden_behavior:
  error_behavior:
  quality_attributes:
  verification_methods:
  required_evidence:
  status:
  version:
```

Requirement types may include:

- functional
- invariant
- safety
- security
- privacy
- performance
- compatibility
- migration
- usability
- accessibility
- observability
- recoverability
- maintainability
- auditability

## 4.9 Test Plan

A structured verification strategy mapped to requirements.

Recommended fields:

```yaml
test_plan:
  id:
  mission_id:
  requirement_coverage:
  failure_models:
  test_layers:
  environments:
  oracles:
  hidden_tests_required:
  independent_generation_required:
  runtime_evidence_required:
  pass_policy:
  unresolved_testability_gaps:
  version:
```

## 4.10 Mission

The central compiled object.

A Mission is an immutable execution and acceptance contract created from:

- workspace context,
- task intent,
- delegation contract,
- scope,
- requirements,
- tests,
- environment,
- agent roles,
- permissions,
- and gates.

Recommended fields:

```yaml
mission:
  id:
  workspace_id:
  task_id:
  version:
  status:
  goal:
  purpose:
  affected_users:
  semantic_scope:
  direct_scope:
  impact_scope:
  exclusions:
  requirements:
  test_plan:
  context_plan:
  environment_spec:
  worker_profile:
  verifier_profiles:
  permissions:
  risk_class:
  gate_requirements:
  unresolved_uncertainty:
  repository_revision:
  created_at:
```

## 4.11 Run

A concrete execution attempt of one Mission version.

A Run must reference:

- exact mission version,
- exact repository revision,
- exact context packet,
- exact environment,
- exact agent profile,
- exact permissions,
- exact tool set.

## 4.12 Evidence

A structured artifact supporting or contradicting a requirement.

Evidence types:

- test result
- static analysis result
- diff
- trace
- log
- benchmark
- security scan
- browser observation
- human review
- model review
- runtime canary
- rollback result
- policy decision
- artifact inspection

## 4.13 Gate Decision

A deterministic or governed decision controlling state transition.

Recommended fields:

```yaml
gate_decision:
  id:
  mission_id:
  gate:
  decision:
  rule_results:
  evidence_refs:
  unresolved_findings:
  approved_by:
  override:
  reason:
  created_at:
```

## 4.14 Sub-workspace

A temporary or persistent child workspace for work that requires its own local world model.

Use a sub-workspace when:

- the work spans multiple dependent tasks,
- local context evolves independently,
- specialized agent roles are required,
- the work has its own risks and requirements,
- or the work is a major migration, subsystem, or program.

Do not create a sub-workspace for every task.

---

# 5. Universal Workspace Context Library

Holodeck should initialize every workspace against the same universal top-level knowledge categories.

The categories remain stable across projects. Their content and required depth vary by project and task.

Each category must have an explicit state:

- provided
- discovered
- inferred
- confirmed
- disputed
- unknown
- not_applicable

## 5.1 Identity and Purpose

Required knowledge:

- project name
- project description
- purpose
- primary outcomes
- non-goals
- maturity stage
- business or organizational context
- criticality

Primary source:

- user or authoritative product source

## 5.2 Stakeholders and Users

Required knowledge:

- primary users
- secondary users
- operators
- administrators
- maintainers
- auditors
- external systems
- affected non-users
- user goals
- user authority
- user expertise
- failure consequences by role

Primary source:

- user, product documentation, domain documentation

## 5.3 Capabilities and Workflows

Required knowledge:

- major capabilities
- actor
- trigger
- preconditions
- normal flow
- alternate flow
- expected outcome
- failure outcome
- adjacent capabilities
- critical user journeys

Sources:

- product documentation
- user input
- code and interface discovery
- analytics or runtime observation

## 5.4 Domain Model

Required knowledge:

- core entities
- relationships
- identity rules
- ownership
- states
- transitions
- terminology
- domain invariants

Sources:

- schemas
- code
- documentation
- domain experts

## 5.5 Technical Architecture

Required knowledge:

- repositories
- components
- services
- modules
- interfaces
- protocols
- dependencies
- trust boundaries
- concurrency model
- synchronous and asynchronous flows
- deployment boundaries
- build graph

Sources:

- automated repository discovery
- architecture documentation
- runtime configuration
- human confirmation

## 5.6 Data and Information Model

Required knowledge:

- data entities
- fields and semantics
- source of truth
- validation
- relationships
- retention
- sensitivity
- migration obligations
- compatibility
- consistency model
- deletion rules

## 5.7 Rules, Invariants, and Policies

Required knowledge:

- architectural rules
- security rules
- privacy rules
- regulatory constraints
- dependency restrictions
- forbidden actions
- approval requirements
- system invariants
- exceptions
- override authority

## 5.8 Quality and Success Model

Required knowledge:

- product success metrics
- reliability targets
- performance targets
- usability expectations
- accessibility requirements
- maintainability expectations
- observability expectations
- acceptable failure rates
- critical failure classes
- trade-off preferences

## 5.9 Risk and Failure Model

Required knowledge:

- threat actors
- user errors
- race conditions
- partial failures
- crashes
- retries
- duplicate actions
- timeouts
- stale data
- malicious inputs
- dependency failures
- cascading failures
- failure impact
- detectability
- reversibility
- mitigation

## 5.10 Operational Environment

Required knowledge:

- runtime versions
- operating systems
- infrastructure
- deployment environments
- external services
- secrets
- permissions
- monitoring
- logging
- tracing
- rollback
- backup
- recovery
- incident response
- resource constraints

## 5.11 Existing Behavior and Compatibility

Required knowledge:

- public contracts
- current behavior
- stored data
- downstream consumers
- undocumented relied-upon behavior
- supported versions
- deprecation policy
- migration obligations

## 5.12 Historical Decisions and Incidents

Required knowledge:

- architecture decisions
- rejected alternatives
- previous incidents
- recurring defects
- previous migrations
- known workarounds
- flaky tests
- prior agent failures
- historical rationale

## 5.13 Verification and Test Capabilities

Required knowledge:

- test frameworks
- existing test suites
- fixtures
- simulation capabilities
- test data
- browser or device access
- available sandboxes
- static analysis
- security tools
- runtime instrumentation
- sources of nondeterminism
- cost and time limits

## 5.14 Governance and Authority

Required knowledge:

- who defines intent
- who approves requirements
- who accepts risk
- who may change policy
- which decisions are delegated
- which decisions require approval
- override policy
- dispute resolution
- incident ownership

## 5.15 Sources, Provenance, and Uncertainty

Required knowledge:

- source registry
- authority ranking
- freshness
- confidence
- assumptions
- conflicts
- unknowns
- superseded knowledge
- verification dates
- generated versus human-provided content

---

# 6. Workspace Genesis

Workspace Genesis is the process that turns raw project material into a usable Workspace Model.

## 6.1 Stage 1: Minimal Intent Seed

The user supplies:

- what the project is,
- who it serves,
- what outcome it creates,
- what is especially important,
- what is especially dangerous,
- and what Holodeck should not decide automatically.

This is the minimum human-owned semantic input.

Example:

```text
This is a local control plane for autonomous coding agents.
Its users are developers, engineering teams, worker agents, and verifiers.
Its purpose is bounded, inspectable autonomous software work.
The main risks are conflicting changes, unauthorized actions, and accepting unverified output.
Prefer correctness and inspectability over maximum speed.
```

## 6.2 Stage 2: Automated Discovery

Holodeck scans:

- repository tree,
- languages,
- package manifests,
- build files,
- test files,
- CI configuration,
- deployment files,
- documentation,
- API specifications,
- schemas,
- configuration,
- ownership files,
- issues and decisions if connected,
- runtime metadata if available.

It populates descriptive categories automatically.

## 6.3 Stage 3: Workspace Curator Analysis

The Workspace Curator proposes:

- project identity,
- technical component map,
- capabilities,
- domain entities,
- important policies,
- context modules,
- agent roles,
- missing knowledge,
- contradictions,
- confidence levels,
- recommended readiness state.

## 6.4 Stage 4: Gap Analysis

The system compares discovered context against the universal schema.

It must identify:

- unknown but blocking context,
- inferred context requiring confirmation,
- conflicting sources,
- stale sources,
- missing operational assumptions,
- missing test oracles,
- missing authority decisions.

## 6.5 Stage 5: Targeted Clarification

Holodeck asks only questions that materially affect:

- requirements,
- scope,
- authority,
- risk,
- or acceptance.

It should not ask users to manually fill every field.

## 6.6 Stage 6: Workspace Proposal

The system generates an inspectable workspace proposal showing:

- confirmed facts,
- inferred facts,
- proposed principles,
- source links,
- conflicts,
- open questions,
- readiness blockers.

## 6.7 Stage 7: Activation

The workspace receives a readiness level.

### Level 0 — Uninterpreted

Repository registered, reliable model absent.

Permitted:

- browsing,
- summarization,
- low-risk assistance.

### Level 1 — Discovered

Technical structure known, semantic context weak.

Permitted:

- code explanation,
- repository navigation,
- limited task suggestions.

### Level 2 — Contextualized

Purpose, users, capabilities, and major constraints defined.

Permitted:

- task planning,
- requirement proposals,
- supervised implementation.

### Level 3 — Governed

Permissions, invariants, risk policies, and authority defined.

Permitted:

- bounded controlled execution.

### Level 4 — Verifiable

Reliable environments, oracles, and independent tests exist.

Permitted:

- autonomous acceptance for approved risk classes.

### Level 5 — Operationally Assured

Deployment, observability, rollback, and incident learning integrated.

Permitted:

- dark-factory lanes where justified.

---

# 7. Intent Kernel and Delegation

## 7.1 Workspace Intent Kernel

The Intent Kernel contains stable, user-approved semantic commitments:

- project purpose
- primary users
- core values
- non-goals
- risk tolerance
- forbidden outcomes
- quality priorities
- trade-off preferences
- authority boundaries

The compiler may instantiate these commitments for a task but may not silently rewrite them.

## 7.2 Decision Classes

Holodeck should distinguish:

### Execution decisions

How to achieve an agreed outcome.

Examples:

- internal function structure
- test organization
- file naming
- implementation details

Default autonomy:

- high

### Optimization decisions

Which trade-off to choose within an accepted range.

Examples:

- simplicity versus extensibility
- speed versus maintainability
- token cost versus context breadth

Default autonomy:

- conditional on known preferences

### Interpretation decisions

What the user meant.

Examples:

- whether “safe” means preventing accidental overlap or enforcing filesystem authority
- whether a feature request implies migration support

Default autonomy:

- cautious; require evidence or clarification when outcome changes materially

### Intent decisions

What the user should value or pursue.

Examples:

- redefining the project purpose
- changing target users
- accepting new risk
- changing product strategy

Default autonomy:

- proposal only; no silent execution

## 7.3 Delegation Levels

### Level 0 — Exact Execution

User defines outcome and implementation.

### Level 1 — Implementation Discretion

User defines outcome. Holodeck chooses technical implementation.

### Level 2 — Bounded Optimization

Holodeck chooses among approved alternatives using explicit preferences.

### Level 3 — Outcome Planning

User defines a high-level objective. Holodeck defines tasks and solutions within a governed scope.

### Level 4 — Strategic Recommendation

Holodeck may propose changes to goals or scope. Human approval required.

### Level 5 — Intent Formation

Holodeck independently decides what the user should want.

This should not be a standard autonomous mode.

## 7.4 Conditions for Autonomous Decisions

Holodeck may decide for the user only when:

- intent clarity is sufficient,
- relevant preferences are known,
- scope is bounded,
- world-model confidence is adequate,
- outcome is observable,
- decision is reversible or explicitly approved,
- risk lies inside the delegated envelope,
- and an independent alignment check finds no material semantic drift.

---

# 8. Task Creation and Mission Compilation

## 8.1 Task Intake

A task begins as:

- user instruction,
- issue,
- generated recommendation,
- incident follow-up,
- failed test,
- migration need,
- or workspace maintenance action.

## 8.2 Task Intent Compiler

The compiler separates:

- literal request,
- desired outcome,
- affected users,
- product purpose,
- non-goals,
- constraints,
- preferences,
- acceptable variation,
- assumptions,
- authority boundaries.

It produces the Delegation Contract.

## 8.3 Scope Analysis

Scope must combine several methods.

### Explicit Scope

Files, components, or exclusions provided by the user.

### Structural Scope

Derived from:

- imports
- call graphs
- dependency graphs
- API relationships
- schemas
- build dependencies
- ownership maps

### Semantic Scope

Derived from:

- product concepts
- capability relationships
- domain entities
- historical decisions
- similar prior tasks

### Change-Impact Scope

Includes downstream systems that may be affected even if they are not edited.

### Risk Scope

Includes areas that must be reviewed because missing them would be high consequence.

The compiler must distinguish:

- **Direct scope:** where edits are allowed or expected.
- **Impact scope:** what must be tested, observed, or reviewed.
- **Forbidden scope:** what must not be changed.
- **Uncertain scope:** areas that may require expansion.

## 8.4 Context Compilation

For every task, the compiler creates:

### Retrieved context

Existing relevant workspace knowledge.

### Instantiated context

General workspace rules applied to the current task.

### Derived context

New task-specific implications produced by reasoning across known facts.

Example:

```text
Workspace rule:
Database changes require backward compatibility.

Task:
Add run_id to claims.

Derived implication:
A migration is required, existing databases must remain readable,
and migration tests are mandatory.
```

Derived context must record:

- source facts,
- inference,
- confidence,
- status,
- applicability,
- and whether approval is required.

## 8.5 Context Plan

Each mission gets a Context Plan that defines:

- mandatory modules,
- role-specific modules,
- retrieved sources,
- generated summaries,
- token budget,
- priority,
- progressive disclosure,
- available retrieval tools,
- excluded sources,
- and provenance.

## 8.6 Role-Specific Context Packets

The following roles should not receive identical context.

### Worker packet

Contains:

- task goal
- requirements
- implementation scope
- permissions
- relevant architecture
- visible tests
- expected outputs

### Test Strategist packet

Contains:

- requirements
- user and system scenarios
- risk model
- architecture
- available verification capabilities
- expected oracles

### Independent Test Generator packet

Contains:

- requirements
- interfaces
- failure hypotheses
- approved test plan
- environment
- relevant implementation only where necessary

### Verifier packet

Contains:

- requirements
- required evidence
- hidden scenarios
- risk policy
- worker output
- test results

### Intent Verifier packet

Contains:

- original request
- intent kernel
- delegation contract
- mission
- autonomous decisions
- final result

---

# 9. Requirements Compiler

## 9.1 Requirement Generation Inputs

The requirement generator should receive:

- project purpose
- affected users
- feature purpose
- normal scenarios
- alternate scenarios
- failure consequences
- domain model
- technical architecture
- current behavior
- compatibility obligations
- quality priorities
- policies
- risks
- operational constraints
- unknowns

## 9.2 Requirement Generation Procedure

For every task:

1. Restate intended outcome.
2. Identify affected actors.
3. Identify capability and workflow.
4. Identify preconditions.
5. Identify normal behavior.
6. Identify alternate flows.
7. Identify failure cases.
8. Identify invariants.
9. Identify authorization requirements.
10. Identify quality obligations.
11. Identify compatibility obligations.
12. Identify operational obligations.
13. Identify observability needs.
14. Identify unresolved ambiguity.
15. Generate structured requirements.
16. Link every requirement to source purpose, risk, or policy.

## 9.3 Requirement Quality Criteria

A good requirement must be:

- necessary
- unambiguous
- bounded
- implementation-independent where possible
- observable
- testable or explicitly marked judgment-based
- traceable
- prioritized
- compatible with authority boundaries
- explicit about failure behavior
- explicit about uncertainty

## 9.4 Requirement Categories Checklist

The compiler should deliberately consider:

- functional behavior
- state transitions
- validation
- error behavior
- authorization
- concurrency
- security
- privacy
- performance
- compatibility
- migration
- observability
- recovery
- usability
- accessibility
- maintainability
- auditability

Not every task requires every category, but exclusion should be deliberate.

---

# 10. Test Strategy Compiler

## 10.1 Most Important Inputs

Reliable test generation depends on:

1. precise requirements
2. explicit invariants
3. realistic failure models
4. correct test boundary
5. reliable oracle
6. relevant architecture
7. reproducible environment
8. independence from implementation
9. existing behavior and compatibility
10. risk and consequence

## 10.2 Failure Model Generation

For each requirement, the Test Strategist should ask:

- What assumptions does this requirement depend on?
- How can timing break it?
- How can state become stale?
- What happens on partial failure?
- What happens on retry?
- What happens on duplicate operation?
- What happens under malicious input?
- What happens if dependencies fail?
- What could pass ordinary tests while still being wrong?
- What failure would be hardest to detect?

## 10.3 Test Layers

Use the necessary combination of:

- unit tests
- component tests
- integration tests
- contract tests
- state-machine tests
- property-based tests
- concurrency tests
- stress tests
- fault-injection tests
- migration tests
- compatibility tests
- browser tests
- end-to-end tests
- security tests
- performance tests
- runtime canary tests
- human or model rubric evaluation

## 10.4 Worker Tests versus Independent Tests

### Worker-generated tests

Purpose:

- implementation feedback
- local correctness
- visible contract coverage

Risk:

- may confirm implementation rather than challenge requirements

### Independent tests

Purpose:

- challenge the implementation
- test hidden edge cases
- validate external behavior
- detect worker blind spots

Independent test generation should receive the requirement and failure model before the worker’s detailed reasoning.

## 10.5 Hidden Holdout Tests

Critical requirements may require tests unavailable to the worker.

Examples:

- adversarial path forms
- concurrency schedules
- production-like malformed data
- security edge cases
- previous escaped defects

## 10.6 Test Oracle

Every test must define:

- correct observation
- incorrect observations
- tolerated uncertainty
- timing limits
- evidence collection
- false-positive risk
- false-negative risk

## 10.7 Regression Learning

Every escaped defect should produce:

- a minimal reproduction
- a permanent regression test
- an updated requirement or failure model
- a workspace learning item
- a review of why existing gates failed

## 10.8 Mutation Testing

Use selectively for critical modules.

The system deliberately introduces small defects to determine whether tests detect them.

Do not make this mandatory for all work because of cost.

---

# 11. Environment Compiler

The Environment Compiler creates the reproducible world in which workers and verifiers operate.

## 11.1 Inputs

- mission
- repository revision
- runtime requirements
- build files
- test framework
- services
- data fixtures
- network policy
- secrets policy
- resource constraints
- operating system assumptions
- concurrency requirements

## 11.2 Outputs

```yaml
environment_spec:
  base_runtime:
  dependency_lock:
  install_commands:
  services:
  test_commands:
  test_data:
  network_policy:
  filesystem_policy:
  secrets:
  resource_limits:
  reset_strategy:
  snapshot_strategy:
  observability:
  supported_platforms:
  version:
```

## 11.3 Required Properties

The environment should be:

- isolated
- reproducible
- disposable
- observable
- resettable
- least-privilege
- versioned
- tied to a repository revision
- auditable

## 11.4 Environment Gaps

If the system cannot reproduce a critical behavior, the mission should:

- remain blocked,
- lower autonomy,
- require human review,
- or explicitly accept reduced assurance.

---

# 12. Gates and State Machines

## 12.1 Task State Machine

Recommended states:

```text
draft
→ definition_review
→ ready
→ in_progress
→ submitted_for_verification
→ verified
→ accepted
→ released
```

Alternative states:

```text
blocked
changes_required
failed
cancelled
release_blocked
```

## 12.2 Run State Machine

Recommended states:

```text
queued
→ active
→ submitted
→ completed
```

Failure states:

```text
failed
cancelled
timed_out
abandoned
```

A run completing does not automatically accept the mission.

## 12.3 Definition Gate

A task cannot become ready until:

- intended outcome is explicit
- affected users are known where relevant
- non-goals are recorded
- scope is sufficiently bounded
- requirements are defined
- risk class is assigned
- test strategy exists
- major unknowns are resolved or accepted
- delegated authority is clear
- mission readiness threshold is met

## 12.4 Execution Gate

A run cannot begin until:

- mission version is fixed
- context packet is compiled
- repository revision is fixed
- agent role is assigned
- permissions are granted
- file or component claims are valid
- no conflicting claims exist
- environment is available
- required tests are defined
- required approvals exist

## 12.5 Completion Gate

A worker can submit a completion candidate only if it provides:

- changed artifacts
- implementation summary
- tests added
- tests run
- known limitations
- requirement-to-evidence mapping
- unresolved uncertainty
- context expansion history
- autonomous decisions made

The mission moves to verified only if:

- all critical requirements have evidence
- mandatory tests pass
- independent verification passes
- no unresolved critical findings remain
- policy checks pass
- intent verification passes where required

## 12.6 Release Gate

Release depends on:

- risk level
- human approvals
- security impact
- migration safety
- rollback capability
- canary result
- observability
- incident plan
- production policy

---

# 13. Policy and Execution Authority

Holodeck must evolve from recording declared activity to controlling actual activity.

## 13.1 Current conceptual distinction

### Record Authority

The system records what an agent says it intends to do.

### Execution Authority

The system controls what the agent can actually do.

Holodeck must develop execution authority through controlled adapters.

## 13.2 Tool Policy

Every tool action should be classified:

- automatic
- approval_required
- denied

Examples:

```text
repository_read → automatic
workspace_write → automatic within claim
network_access → approval_required
dependency_install → conditional
production_deploy → approval_required
destructive_data_change → denied or strong approval
```

## 13.3 Least Privilege

Every run receives only:

- required filesystem scope
- required network scope
- temporary credentials
- approved tools
- resource limits
- time limits

## 13.4 Claims

Claims should be:

- canonicalized
- workspace-relative
- transactionally exclusive
- linked to real run identity
- time-bound where appropriate
- auditable
- recoverable
- enforceable where possible

Direct file scope and conceptual impact scope should remain distinct.

---

# 14. Intent Verification and Semantic Handoff

Technical correctness is insufficient.

Holodeck must evaluate whether the delivered result preserves the user’s actual intent.

## 14.1 Semantic Acceptance Dimensions

### Requirement correctness

Did the system satisfy explicit requirements?

### Intent fidelity

Does the result preserve the purpose and expected outcome?

### Scope fidelity

Did the system stay inside delegated scope?

### Trade-off fidelity

Were choices resolved according to approved preferences?

### Authority fidelity

Did Holodeck make only decisions it was allowed to make?

### Assumption validity

Were important assumptions confirmed or disclosed?

### Outcome usefulness

Does the result solve the actual problem rather than merely pass tests?

## 14.2 Intent Verifier

A separate agent or process compares:

- original request
- workspace intent kernel
- delegation contract
- mission
- implementation plan
- autonomous decisions
- final result
- verification evidence

It searches for:

- added goals
- omitted constraints
- altered priorities
- silent scope expansion
- unsupported assumptions
- decisions outside authority
- technically correct but semantically wrong output

## 14.3 Semantic Acceptance Tests

Examples:

- mandatory workspace rules are never omitted
- inferred context is never labelled as confirmed fact
- implementation does not redefine product purpose
- context limits do not remove critical safety requirements
- unknown migration policy blocks autonomous schema changes
- worker cannot authorize its own expanded scope
- final output matches the intended user outcome

## 14.4 Final Handoff Artifact

Every completed mission should return:

```yaml
handoff:
  requested_outcome:
  delivered_outcome:
  intent_mapping:
  requirements_satisfied:
  evidence:
  autonomous_decisions:
  deviations:
  assumptions:
  unresolved_uncertainty:
  known_limitations:
  rollback_or_recovery:
  recommended_followups:
```

---

# 15. Continuous Workspace Maintenance

Workspace Genesis is not one-time.

## 15.1 Refresh Triggers

Reevaluate workspace context when:

- architecture files change
- CI changes
- dependencies change
- services are introduced
- schema changes
- incidents occur
- user corrects an interpretation
- tasks repeatedly request missing context
- an agent discovers undocumented constraints
- verification exposes a missing invariant
- policy changes
- external dependencies change

## 15.2 Targeted Invalidation

Do not rebuild the whole workspace automatically.

Example:

```text
Database schema changed
→ mark data-model context stale
→ mark migration-policy context for review
→ invalidate affected task packets
→ refresh relevant tests
```

## 15.3 Learning Loop

Every failure should improve one or more layers:

```text
Wrong requirement
→ improve user or product model

Missed dependency
→ improve scope graph

Missing context
→ improve source map

Weak test
→ improve failure model or oracle

Environment mismatch
→ improve environment compiler

Policy violation
→ improve execution enforcement

Production defect
→ add regression test and incident learning
```

---

# 16. Readiness and Confidence

Do not use one vague confidence number.

Track separate dimensions:

- purpose clarity
- user-model confidence
- scope confidence
- requirement completeness
- technical-context coverage
- environment reproducibility
- oracle quality
- security-boundary confidence
- operational-context coverage
- intent fidelity confidence
- authority clarity

Example:

```yaml
readiness:
  purpose_clarity: high
  user_model: high
  scope_confidence: medium
  requirements: high
  oracle_quality: high
  environment_reproducibility: low
  authority_clarity: high
```

Risk class determines required thresholds.

---

# 17. Suggested Service Architecture

```text
holodeck/
├── kernel/
│   ├── state_machine.py
│   ├── policy_engine.py
│   ├── gate_engine.py
│   ├── authorization.py
│   ├── claims.py
│   ├── provenance.py
│   └── migrations.py
│
├── workspace/
│   ├── genesis.py
│   ├── schema.py
│   ├── curator.py
│   ├── source_registry.py
│   ├── context_library.py
│   ├── context_modules.py
│   ├── readiness.py
│   └── refresh.py
│
├── intent/
│   ├── intent_kernel.py
│   ├── task_interpreter.py
│   ├── delegation_contract.py
│   ├── decision_rights.py
│   └── intent_verifier.py
│
├── mission/
│   ├── compiler.py
│   ├── scope_analyzer.py
│   ├── context_compiler.py
│   ├── requirement_compiler.py
│   ├── test_strategy_compiler.py
│   ├── environment_compiler.py
│   ├── risk_classifier.py
│   └── mission_schema.py
│
├── agents/
│   ├── profiles.py
│   ├── curator_agent.py
│   ├── requirement_agent.py
│   ├── test_strategist_agent.py
│   ├── worker_adapter.py
│   ├── independent_test_agent.py
│   ├── verifier_agent.py
│   └── model_router.py
│
├── execution/
│   ├── sandbox.py
│   ├── tool_gateway.py
│   ├── repository_adapter.py
│   ├── filesystem_policy.py
│   ├── network_policy.py
│   ├── environment_builder.py
│   └── run_controller.py
│
├── verification/
│   ├── evidence_store.py
│   ├── test_runner.py
│   ├── oracle.py
│   ├── hidden_tests.py
│   ├── static_checks.py
│   ├── runtime_checks.py
│   └── semantic_checks.py
│
├── learning/
│   ├── incident_ingestion.py
│   ├── regression_generator.py
│   ├── context_updater.py
│   └── calibration.py
│
├── api/
│   ├── workspaces.py
│   ├── tasks.py
│   ├── missions.py
│   ├── runs.py
│   ├── evidence.py
│   ├── approvals.py
│   └── handoffs.py
│
├── storage/
│   ├── models.py
│   ├── repositories.py
│   ├── event_store.py
│   └── migrations/
│
├── ui/
│   ├── workspace_genesis/
│   ├── context_library/
│   ├── mission_inspector/
│   ├── gate_dashboard/
│   ├── evidence_viewer/
│   └── handoff_view/
│
└── tests/
    ├── unit/
    ├── integration/
    ├── concurrency/
    ├── property/
    ├── security/
    ├── migration/
    ├── end_to_end/
    └── semantic/
```

This is a target architecture, not a requirement to create every folder immediately.

---

# 18. Suggested Persistence Model

Recommended relational entities:

- workspaces
- workspace_versions
- sources
- context_items
- context_modules
- context_module_items
- agent_profiles
- intent_kernels
- tasks
- delegation_contracts
- requirements
- missions
- mission_context_items
- test_plans
- test_cases
- environments
- runs
- claims
- tool_invocations
- approvals
- evidence
- gate_decisions
- handoffs
- incidents
- learning_items
- schema_migrations

Use relational columns for:

- identity
- relationships
- state
- authority
- timestamps
- versioning
- query-critical values

Use JSON only for:

- flexible metadata
- model-generated structured output
- adapter-specific payloads

Do not store critical relationships only inside JSON.

---

# 19. Initial API Surface

## Workspace

```text
POST   /api/workspaces
GET    /api/workspaces/{id}
POST   /api/workspaces/{id}/genesis
GET    /api/workspaces/{id}/context
POST   /api/workspaces/{id}/context/refresh
POST   /api/workspaces/{id}/context/confirm
GET    /api/workspaces/{id}/readiness
```

## Sources and Context

```text
POST   /api/workspaces/{id}/sources
GET    /api/workspaces/{id}/sources
POST   /api/workspaces/{id}/context-items
PATCH  /api/workspaces/{id}/context-items/{context_id}
POST   /api/workspaces/{id}/context-modules
```

## Tasks and Missions

```text
POST   /api/workspaces/{id}/tasks
POST   /api/tasks/{id}/compile
GET    /api/tasks/{id}/delegation-contract
GET    /api/tasks/{id}/mission
POST   /api/tasks/{id}/approve-definition
```

## Runs

```text
POST   /api/missions/{id}/runs
GET    /api/runs/{id}
POST   /api/runs/{id}/submit
POST   /api/runs/{id}/context-request
POST   /api/runs/{id}/cancel
```

## Evidence and Gates

```text
POST   /api/runs/{id}/evidence
GET    /api/missions/{id}/evidence
POST   /api/missions/{id}/verify
GET    /api/missions/{id}/gates
POST   /api/missions/{id}/gates/{gate}/decide
```

## Handoff

```text
GET    /api/missions/{id}/handoff
POST   /api/missions/{id}/accept
POST   /api/missions/{id}/reject
```

---

# 20. Implementation Roadmap

## Phase 0 — Correct the Existing Runtime

### Objectives

Make current coordination guarantees real before adding more intelligence.

### Work

- make claim acquisition transactionally exclusive
- normalize and validate paths
- enforce workspace roots and exclusions
- add explicit run_id to claims
- define task and run state machines
- add request schema validation
- add structured API errors
- add database migrations
- enable foreign keys
- add authentication for non-local use
- add CI
- add concurrency tests
- harden Docker

### Exit criteria

- overlapping concurrent claims cannot both succeed
- invalid paths are rejected
- task and run states cannot become nonsensical
- old databases migrate safely
- all critical invariants have tests
- CI is required for merge

## Phase 1 — Workspace Schema and Provenance

### Objectives

Create the persistent structured workspace model.

### Work

- implement universal context categories
- implement source registry
- implement context items
- implement context modules
- implement epistemic states
- implement authority and confidence metadata
- implement workspace versioning
- implement readiness dimensions
- build workspace inspection UI

### Exit criteria

- a workspace can represent purpose, users, architecture, policies, unknowns, and provenance
- every context item has a source and epistemic type
- conflicts and unknowns are visible
- workspace versions are immutable

## Phase 2 — Workspace Genesis

### Objectives

Populate the workspace model from user intent and repository discovery.

### Work

- minimal intent seed flow
- repository scanner
- documentation scanner
- test and build discovery
- architecture inference
- context category gap analysis
- curator proposal
- targeted clarification flow
- workspace activation
- readiness level assignment

### Exit criteria

- new repository onboarding produces a structured workspace proposal
- inferred items are not confused with confirmed facts
- missing critical context is surfaced
- human confirmation is supported
- low-confidence workspaces cannot enter unsafe autonomy levels

## Phase 3 — Intent Kernel and Delegation Contracts

### Objectives

Preserve user intent and define decision authority.

### Work

- intent kernel object
- preference hierarchy
- non-goals
- forbidden outcomes
- decision rights
- delegation levels
- delegation contract compiler
- assumption tracking
- semantic acceptance criteria

### Exit criteria

- every compiled task has a delegation contract
- autonomous decisions are classifiable
- high-impact interpretation decisions require approval
- final handoff can compare delivered output with intended outcome

## Phase 4 — Mission Compiler

### Objectives

Turn tasks into versioned executable missions.

### Work

- scope analyzer
- direct versus impact scope
- risk classifier
- context compiler
- context packet versioning
- task-specific derived context
- mission schema
- role assignment
- sub-workspace rules
- mission inspection UI

### Exit criteria

- every run references an immutable mission
- every mission has scope, exclusions, context, permissions, risk, and roles
- derived context is traceable
- context packets are role-specific
- context expansion requests are supported

## Phase 5 — Requirements and Test Strategy

### Objectives

Compile requirements and verification plans from meaning and risk.

### Work

- structured requirements
- requirement categories
- requirement traceability
- test strategist role
- failure model generation
- oracle definitions
- test plan objects
- requirement-to-test mapping
- hidden test support
- regression learning

### Exit criteria

- every critical requirement maps to evidence
- workers cannot unilaterally define acceptance
- independent tests can be generated
- testability gaps can block autonomy
- escaped defects become regression artifacts

## Phase 6 — Environment Compiler

### Objectives

Create reproducible controlled execution and verification environments.

### Work

- environment specification
- sandbox builder
- dependency locking
- disposable data services
- network controls
- filesystem controls
- secret handling
- snapshots
- reset
- logs and traces
- platform matrix

### Exit criteria

- run environment can be recreated
- worker and verifier operate in isolated environments
- tool use is observable
- environment gaps reduce autonomy or block execution

## Phase 7 — Gate and Evidence Engine

### Objectives

Make acceptance evidence-based.

### Work

- definition gate
- execution gate
- completion gate
- release gate
- evidence store
- deterministic gate rules
- human approvals
- independent verifier
- intent verifier
- handoff artifact

### Exit criteria

- worker cannot self-accept
- critical transitions require evidence
- semantic drift is checked
- overrides are attributed
- handoff explains what changed, why, and with what uncertainty

## Phase 8 — Controlled Agent Adapters

### Objectives

Connect real worker agents through the governed runtime.

### Work

- repository adapter
- coding agent adapter
- tool gateway
- permission enforcement
- model routing
- context delivery
- run monitoring
- context expansion
- cancellation
- recovery

### Exit criteria

- agents act only through controlled tools
- actions are recorded
- permissions are enforced
- completion candidates include evidence
- abandoned runs can be recovered

## Phase 9 — Operational Assurance

### Objectives

Support production-grade autonomous lanes.

### Work

- canary deployment
- rollback automation
- runtime invariant monitoring
- incident ingestion
- escaped defect analysis
- calibration metrics
- policy audits
- long-term context maintenance

### Exit criteria

- selected low-risk lanes can operate without routine human source review
- runtime failures feed back into requirements, context, and tests
- false acceptance is monitored
- autonomy can be expanded or reduced based on evidence

---

# 21. Product Metrics

Avoid lines of code, number of agents, or number of generated pull requests as primary success metrics.

Track:

- requirement coverage
- scenario success rate
- false acceptance rate
- escaped defect rate
- regression rate
- human intervention rate
- unauthorized decision rate
- semantic divergence rate
- assumption failure rate
- context correction rate
- context retrieval precision
- context omission incidents
- autonomous completion rate
- cost per accepted mission
- time from intent to accepted outcome
- mean time to detect
- mean time to recover
- rollback success rate
- architectural drift rate
- percentage of failures converted into durable learning
- user correction rate
- preference prediction calibration
- task acceptance without directional revision

The most important metrics are:

> How often does Holodeck confidently accept work that should have been rejected?

and:

> How often does Holodeck deliver something technically valid but meaningfully different from what the user intended?

---

# 22. Anti-Patterns to Avoid

## 22.1 One giant workspace system prompt

Why it fails:

- becomes stale
- becomes contradictory
- is difficult to audit
- overloads agents
- mixes authority levels

## 22.2 One all-powerful curator agent

Why it fails:

- opaque
- inconsistent
- high blast radius
- correlated mistakes
- difficult to reproduce

## 22.3 Worker generates all tests and decides completion

Why it fails:

- implementation bias
- reward hacking
- weak independence
- incomplete failure models

## 22.4 Code as the sole source of truth

Why it fails:

- code reveals current behavior, not necessarily intended behavior
- policies and product meaning may live elsewhere
- bugs become interpreted as requirements

## 22.5 User fills a giant onboarding form

Why it fails:

- poor usability
- users may not know technical answers
- information becomes stale
- encourages invented answers

Use minimal intent seed + automated discovery + targeted questions.

## 22.6 Treating generated summaries as authority

Generated summaries must always link to sources and remain labelled as generated.

## 22.7 Silent context expansion

Any material expansion of scope or context must be recorded and may require gates to rerun.

## 22.8 Arbitrary status strings

Use explicit state machines and validated transitions.

## 22.9 Policy as documentation only

Policy must eventually sit on the execution path and enforce tool use.

## 22.10 “Maximum autonomy” as the product objective

The objective is maximum **justified** autonomy.

---

# 23. Example End-to-End Mission

## User request

> Make file claims concurrency-safe.

## Workspace context

```text
Purpose:
Coordinate bounded autonomous software work.

Core principle:
Conflicting work must be prevented rather than repaired later.

Technical reality:
SQLite is the coordination authority.
The HTTP server handles concurrent requests.

Existing behavior:
Claim overlap is checked before insert.

Policy:
Coordination invariants must be enforced transactionally.
```

## Delegation contract

```yaml
intended_outcome:
  Prevent overlapping active claims under concurrent requests.

required_properties:
  - exactly one conflicting request succeeds
  - no partial run remains
  - non-conflicting requests remain parallel
  - existing databases remain compatible

acceptable_variation:
  - transaction strategy may vary
  - internal helper structure may vary

forbidden_outcomes:
  - adding external distributed locking without justification
  - weakening exclusivity
  - silently dropping compatibility

delegated_decisions:
  - choose SQLite transaction implementation
  - organize tests
  - refactor claim helper code

must_escalate:
  - schema change without migration policy
  - changing claim semantics
```

## Derived requirements

```text
REQ-1: Overlapping active claims cannot coexist in one workspace.
REQ-2: Claim acquisition must be atomic.
REQ-3: Failed acquisition must leave no partial run or claim.
REQ-4: Non-overlapping claims may proceed concurrently.
REQ-5: Equivalent normalized paths must be treated as the same surface.
REQ-6: Existing databases must remain readable.
```

## Test plan

```text
Unit:
- path overlap logic

Property:
- generated equivalent path forms

Integration:
- two concurrent SQLite connections

API:
- simultaneous conflicting requests

Migration:
- open old database and upgrade safely

Failure:
- forced error during claim insertion

Holdout:
- parent/child path race
- repeated completion
- stale claim recovery
```

## Completion criteria

- all critical tests pass
- exactly one conflicting request succeeds
- no duplicate active claims exist
- migration test passes
- independent verifier accepts
- intent verifier finds no semantic drift
- handoff explains implementation and limitations

---

# 24. Immediate Actionable Backlog

## Epic A — Runtime Correctness

- [ ] Add explicit database migration framework
- [ ] Enable foreign keys
- [ ] Implement transactional claim acquisition
- [ ] Normalize and validate paths
- [ ] Enforce artifact roots and exclusions
- [ ] Add run_id to claims
- [ ] Add strict task state machine
- [ ] Add strict run state machine
- [ ] Add structured API error model
- [ ] Add concurrency tests
- [ ] Add malformed input tests
- [ ] Add migration tests
- [ ] Add CI

## Epic B — Workspace Context Foundation

- [ ] Define Workspace schema
- [ ] Define Source schema
- [ ] Define Context Item schema
- [ ] Define Context Module schema
- [ ] Define epistemic states
- [ ] Define authority levels
- [ ] Define confidence and freshness fields
- [ ] Build source registry
- [ ] Build context library API
- [ ] Build context inspection UI

## Epic C — Workspace Genesis

- [ ] Create minimal intent seed flow
- [ ] Build repository scanner
- [ ] Build test/build/deployment discovery
- [ ] Build documentation scanner
- [ ] Build category gap analyzer
- [ ] Build curator proposal format
- [ ] Build clarification question generator
- [ ] Build workspace readiness engine
- [ ] Build activation workflow

## Epic D — Intent and Delegation

- [ ] Implement Intent Kernel
- [ ] Implement user preference hierarchy
- [ ] Implement non-goals and forbidden outcomes
- [ ] Implement decision-rights matrix
- [ ] Implement Delegation Contract
- [ ] Implement delegation levels
- [ ] Add semantic acceptance tests
- [ ] Add Intent Verifier

## Epic E — Mission Compiler

- [ ] Define Mission schema
- [ ] Build task interpreter
- [ ] Build direct scope analyzer
- [ ] Build impact scope analyzer
- [ ] Build risk classifier
- [ ] Build context compiler
- [ ] Build derived-context provenance
- [ ] Build role assignment
- [ ] Build immutable context packets
- [ ] Build context expansion requests
- [ ] Define sub-workspace creation rules

## Epic F — Requirements and Tests

- [ ] Define Requirement schema
- [ ] Build requirement compiler
- [ ] Build requirement quality checks
- [ ] Define Test Plan schema
- [ ] Build failure model generator
- [ ] Build oracle schema
- [ ] Build Test Strategist
- [ ] Build requirement-to-test traceability
- [ ] Build independent test generation
- [ ] Build hidden test support
- [ ] Build regression learning

## Epic G — Environment and Execution

- [ ] Define Environment Spec
- [ ] Build isolated sandbox
- [ ] Build dependency installer
- [ ] Build service provisioning
- [ ] Build network policy
- [ ] Build filesystem policy
- [ ] Build secret injection
- [ ] Build snapshot/reset
- [ ] Build tool gateway
- [ ] Build repository adapter
- [ ] Build worker adapters
- [ ] Build run recovery

## Epic H — Evidence and Gates

- [ ] Define Evidence schema
- [ ] Define Gate Decision schema
- [ ] Build Definition Gate
- [ ] Build Execution Gate
- [ ] Build Completion Gate
- [ ] Build Release Gate
- [ ] Build independent verifier
- [ ] Build semantic handoff
- [ ] Build override workflow
- [ ] Build evidence dashboard

---

# 25. Guidance for Coding Agents Using This Document

When converting this specification into an implementation plan:

1. Do not implement the entire target architecture at once.
2. Begin with Phase 0 and establish correctness.
3. Preserve existing working behavior unless explicitly replaced.
4. Create schemas and state machines before agent orchestration.
5. Add tests before or alongside every new invariant.
6. Keep deterministic authority separate from LLM judgment.
7. Store critical relationships relationally, not only in JSON.
8. Make every generated interpretation traceable.
9. Treat unknown context as a first-class state.
10. Do not add agent autonomy before permissions and evidence gates exist.
11. Prefer a modular monolith initially.
12. Keep external dependencies minimal and justified.
13. Make APIs versioned and explicit.
14. Make every state transition auditable.
15. Build thin vertical slices that can be tested end to end.

## Recommended first implementation slice

Build a complete thin slice for:

```text
Workspace creation
→ context item registration
→ task creation
→ delegation contract
→ mission compilation
→ requirement creation
→ definition gate
→ run creation
→ completion candidate
→ evidence attachment
→ completion gate
→ handoff
```

The first slice may use deterministic stubs instead of live agents.

This validates the domain architecture before agent integration.

---

# 26. Final Product Definition

Holodeck is:

> A governed workspace compiler and runtime that converts human intent and project knowledge into bounded, versioned software missions; supplies agents with role-specific context and authority; generates requirements and verification strategies; creates reproducible execution environments; controls state transitions through evidence; and verifies both technical correctness and semantic fidelity before accepting work.

Its core artifact is:

> A compiled Mission backed by a Delegation Contract.

Its core safety model is:

> Agents may reason and propose. The kernel controls authority, gates, provenance, and acceptance.

Its core learning model is:

> Every failure, correction, and completed mission improves the workspace model, requirement library, test suite, and future context compilation.

Its core success criterion is:

> The user receives the outcome they intended, within the authority they delegated, supported by sufficient technical and semantic evidence.
