# 7. Test planning and test generation

> Mechanical Markdown transcription of the canonical source. The DOCX remains authoritative for layout and inline styling.

## 7. Test planning and test generation

Reliable test generation depends first on meaningful requirements, then on a failure model, the correct testing boundary, and an objective oracle. Repository context alone is not sufficient, and excessive implementation detail can bias a test agent into confirming the implementation rather than challenging the requirement.

### 7.1 Separation of roles

| Role | Responsibility | Authority limits |
| --- | --- | --- |
| Requirement Curator | Convert purpose, users, scenarios, and risks into candidate requirements. | Cannot independently accept requirements that require approval. |
| Test Planner | Design failure model, test layers, boundaries, oracles, and coverage map. | Does not modify production implementation. |
| Worker | Implement change and create development tests. | Cannot be sole acceptance authority. |
| Independent Test Implementer | Implement approved adversarial and acceptance tests. | Cannot lower requirements or alter worker code to pass tests. |
| Verifier / Gate Evaluator | Evaluate evidence against requirements and policy. | Must operate within defined jurisdiction and record uncertainty. |

### 7.2 Required inputs for test planning

- Approved requirements and invariants.
- Project and feature purpose relevant to those requirements.
- Affected users, workflows, scenarios, and failure consequences.
- Risk classification and rigor expectations.
- Public interfaces and observable outcomes.
- Architecture and execution environment.
- Known failure history and prior regression cases.
- Testability and resource constraints.
### 7.3 Failure model

The test planner must explicitly enumerate how the requirement could be violated. It should consider ordinary incorrectness, edge cases, partial failure, concurrency, stale state, retries, malformed inputs, authorization, crash recovery, and cross-component interaction where relevant.

```text
FailureHypothesis
  id
  requirement_id
  preconditions
  triggering_action
  expected_violation
  observable_signal
  likelihood
  impact
  proposed_test_boundary
  oracle
  hidden_from_worker   # boolean where holdout value is needed
```

### 7.4 Correct testing boundary

| Boundary | What it can prove | Common limitation |
| --- | --- | --- |
| Unit | Local transformation or decision behavior. | Cannot prove interaction, persistence, or concurrency behavior. |
| Component / store | Component contracts and persistence semantics. | May omit API and process behavior. |
| Integration | Interaction between real components and dependencies. | May still omit actual user/agent workflow. |
| API | External contract, validation, state transitions, and concurrency through service boundary. | May not prove real tool enforcement. |
| End-to-end | Full workflow across adapters, repository, gates, and evidence. | Higher cost and harder diagnosis. |
| Runtime / canary | Behavior under realistic production conditions. | Detects rather than prevents some defects. |

### 7.5 Test oracle

Every generated test must define how correctness is judged. A test without a reliable oracle is merely an experiment.

- For deterministic behavior, define exact state, output, event, and side-effect expectations.
- For non-deterministic or quality requirements, define a rubric, evaluator identity, confidence threshold, disagreement policy, and human-review condition.
- Oracles MUST include forbidden outcomes and partial-state checks, not only the desired success response.
### 7.6 Staged context to reduce bias

1. Black-box phase. Provide requirements, public interfaces, inputs, outputs, state rules, and failure semantics. Generate behavior-driven tests without implementation details.
1. Architecture-risk phase. Provide component boundaries, persistence model, concurrency model, platform assumptions, and external dependencies. Generate architecture-specific failure tests.
1. White-box phase. Provide the exact candidate revision and internals for targeted branch, mutation, and regression tests.
### 7.7 Layered verification strategy

| Layer | Purpose |
| --- | --- |
| Worker development tests | Fast implementation feedback; useful but not independent. |
| Deterministic repository checks | Existing tests, type checks, static analysis, schema and architecture rules. |
| Independent requirement tests | Tests derived from requirements rather than worker implementation. |
| Adversarial tests | Actively search for boundary, security, failure, and state violations. |
| Hidden holdouts | Prevent overfitting to visible acceptance examples. |
| Property-based tests | Generate broad input/state combinations against general invariants. |
| Regression tests | Preserve every validated escaped failure as executable knowledge. |
| Selective mutation tests | Check whether critical tests detect deliberately introduced faults. |
| Runtime evidence | Canary, monitoring, invariant checks, and rollback signals. |

### 7.8 Test plan object

```text
TestPlan
  id
  revision
  task_id
  based_on_requirements[]
  risk_classification
  failure_hypotheses[]
  required_test_layers[]
  requirement_coverage[]
  test_oracles[]
  environment_requirements[]
  hidden_holdouts[]
  independent_verification_required
  human_evaluation_required
  pass_policy
  known_limitations[]
  approval_status
```

### 7.9 Test-generation permissions

- Test agents MAY read approved requirements, interfaces, architecture, and permitted implementation revisions.
- They MAY create tests in an isolated test branch or workspace and execute approved commands.
- They MUST NOT edit approved requirements, lower thresholds, delete failing tests, or modify the worker implementation merely to satisfy their tests.
- Holdout tests and evaluator prompts MUST be access-controlled from the worker where independence is required.
### 7.10 Failure-to-learning loop

```text
Escaped or verification failure
  -> classify failure
  -> create minimal reproduction
  -> link affected requirement
  -> add regression test
  -> update failure model
  -> propose requirement/context/policy change
  -> validate and promote learning
```

### 7.11 Acceptance criteria

- Every critical requirement maps to at least one objective oracle and an appropriate test boundary.
- Test planning can occur independently from worker reasoning.
- The system records whether each test is worker-authored, independently generated, hidden, or runtime-derived.
- A passing suite cannot satisfy a requirement unless requirement-to-evidence coverage is explicit.
- Validated failures automatically produce regression-learning candidates.
