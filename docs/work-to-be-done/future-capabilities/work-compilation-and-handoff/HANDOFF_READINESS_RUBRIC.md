# Handoff readiness rubric

A work package is ready for assignment only when a fresh, competent agent can
reliably discover, understand, implement, and verify its bounded work without
using an unavailable conversation as hidden context.

## Required checks

| Check | Question |
| --- | --- |
| Direction | Does the package state the outcome and applicable product/workspace direction? |
| Boundary | Are scope, non-goals, and deferrals explicit? |
| Authority | Are actor, role, permissions, required approvals, and escalation path clear? |
| Decisions | Are foundational choices locked, local, deferred, or blocking? |
| Context | Are sources ranked by authority/trust, with omission reasons and retrieval paths? |
| Ownership | Does every required capability, record, or interface have an owner? |
| Dependencies | Are prerequisite records, tasks, and artifacts present and ordered? |
| Contract | Are inputs, outputs, invariants, failure modes, and mutation boundaries specified? |
| Oracle | Are success, rejection, and forbidden-side-effect expectations observable? |
| Baseline | Is the repository, environment, and compatibility baseline reproducible? |
| Handoff | Can a role-specific agent identify its first action, stop conditions, and expected evidence? |

## Outcomes

- **ready:** all required checks pass for the task's risk class.
- **ready with bounded unknowns:** permitted only for exploratory work; unknowns,
  limits, and evidence expectations are explicit.
- **needs clarification:** material intent, authority, scope, or acceptance
  ambiguity remains.
- **blocked:** a prerequisite, required source, decision, or environment is
  unavailable.

This is a work-readiness assessment, not a completion or acceptance decision.
