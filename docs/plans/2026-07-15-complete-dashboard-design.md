# Complete dashboard design

## Product boundary

The dashboard is the operator surface for standalone Holodeck. It reflects every capability implemented by the service: workspace intent and scope, tasks and their detailed constraints, agent runs, active and released path claims, service binding and database configuration, project manifest defaults, and onboarding action policy. Features that are not implemented remain visible only in an explicit capability ledger; they are never presented as working controls.

## Information architecture

The interface retains the warm, mineral-paper wabi-sabi visual system and divides the product into four operational views. Overview summarizes health, workload, policy posture, and workspace intent. Work exposes the complete task record and permits workspace/task creation and task status changes. Runs shows agent intent, claimed paths, overlap protection, and run completion. Configuration exposes the effective service settings, manifest schema, all policy actions, workspace boundaries, and the current-versus-planned capability ledger.

Navigation swaps views rather than scrolling to decorative anchors. A persistent workspace selector scopes all operational views. A detail drawer is used for task inspection, while focused forms use accessible modal dialogs.

## API and state flow

The browser loads `/health`, `/api/config`, and `/api/workspaces`, then loads tasks, runs, and claims for the selected workspace. Mutations use explicit endpoints for workspace creation/update, task creation/update, run creation, and run completion. Every successful mutation refreshes authoritative state from the API. The browser does not invent policy or status values.

The runtime adds read models for runs and claims and releases claims atomically when a run completes. Configuration reports the service binding, database location, default project manifest, onboarding policy, and capability status. The policy is labelled accurately as project onboarding policy rather than runtime authorization enforcement.

## Failure handling and verification

API failures produce a visible toast and preserve the last valid view. Empty states explain the next valid action. Forms validate required identifiers and titles before submission; the runtime remains authoritative for path-overlap rejection. Store tests cover updates, run completion, and claims. HTTP tests cover configuration and the full control-plane lifecycle. Browser verification covers desktop and narrow layouts, navigation, dialogs, detail inspection, mutations, and console errors.
