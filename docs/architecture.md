# Alpha architecture

The alpha has one authority: a local SQLite database owned by the runtime. The HTTP API and CLI are adapters over the same store. Records are deliberately small JSON documents so export/import and future schema evolution remain straightforward.

The portable core includes workspaces, tasks, agent runs, and file-path claims. It excludes product-specific conversation memory, semantic retrieval, Telegram, OpenClaw, personal paths, and deployment credentials. Docker Compose supplies a reference deployment, not a required hosting model.

The bundled dashboard is an adapter over that same authority. It reads effective runtime configuration, workspace state, task details, runs, and claims from the API; it can create and update the records supported by the alpha. Completing a run atomically releases its active claims. Planned capabilities are reported separately from available controls so the product boundary remains explicit.

The next extraction phase should port evidence, handoff, and repository-observation contracts from the existing system only after their generic schema and policy boundaries are documented and tested here.

## Onboarding and safety

`holodeck init` recognizes only Git repositories and writes a project-local manifest and policy. It is non-invasive by design. The policy records deny-by-default and approval-required decisions, but it is advisory: the runtime does not intercept, authorize, or block actions until enforcement adapters exist. This keeps the boundary explicit without claiming a sandbox that has not been built.
