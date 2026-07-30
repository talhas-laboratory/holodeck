# Structured reviewer-worker feedback

## Purpose

Create a closed, revision-oriented review protocol where findings attach to exact work and remain accountable through resolution or escalation.

## Required records

- `CandidateRevision`: immutable base/result repository revisions, diff, changed files, completion candidate, hash.
- `ReviewRequest` and `Review`: reviewer role/revision, jurisdiction, review position packet, exact revision, recommendation, findings.
- `Finding` and `FindingResponse`: category, severity, blocking status, anchors, requested change, evidence, acceptance conditions, response type, remaining risk, and disposition.

## Workflow

Review purpose/requirements/diff/tests/architecture before the worker narrative, then inspect trace and run adversarial verification. A response creates a new revision; reviewers explicitly resolve, reopen, modify, withdraw, accept risk, supersede, waive, or escalate findings. Blocking authority is constrained by role jurisdiction.

## Acceptance

Every finding has an anchor and requested outcome. Workers answer each blocking finding individually. Reviewers receive task-position context and exact deltas. Review recommendations are inputs to the gate engine, never final acceptance.
