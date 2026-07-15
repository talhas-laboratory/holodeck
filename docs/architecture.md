# Alpha architecture

The alpha has one authority: a local SQLite database owned by the runtime. The HTTP API and CLI are adapters over the same store. Records are deliberately small JSON documents so export/import and future schema evolution remain straightforward.

The portable core includes workspaces, tasks, agent runs, and file-path claims. It excludes product-specific conversation memory, semantic retrieval, Telegram, OpenClaw, personal paths, and deployment credentials. Docker Compose supplies a reference deployment, not a required hosting model.

The next extraction phase should port evidence, handoff, and repository-observation contracts from the existing system only after their generic schema and policy boundaries are documented and tested here.
