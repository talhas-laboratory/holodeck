# Work graph, structured requirements, and gates

## Purpose

Make task meaning explicit before execution. Requirements derive from purpose, users, scenarios, risk, and surrounding work—not code alone.

## Required model

Use a typed, versioned relational work hierarchy; a graph database is optional. Every execution-ready task has a `TaskPosition` explaining its parent outcome/capability/feature, purpose, affected users, scope, non-goals, dependencies, consumers, parallel work, risks, and invariants.

Requirements are structured obligations with rationale, scenarios, acceptance conditions, required evidence, ownership, approval, and trace links. A gate engine owns Definition, Execution, Review Submission, Review Approval, Verification, and Acceptance decisions, explaining every pass/fail result.

## Rules and acceptance

Workers and reviewers may not silently expand task scope. Definition gaps create correction or new-task proposals. Every blocking requirement has acceptance conditions and evidence; requirements trace through evidence, review, and final acceptance.
