# M1 module contracts

Canonical ownership for the durable governance kernel. Source of truth for
machine checks: `holodeck_governance.domain.vocabulary`.

## Layer rules

| Layer | Package | May import | Must not import |
| --- | --- | --- | --- |
| Domain | `holodeck_governance.domain` | stdlib typing/dataclasses/enums; other domain submodules | `application`, `storage`, `holodeck_control_plane`, `sqlite3`, HTTP/MCP/SDK |
| Application | `holodeck_governance.application` | `domain`; repository **protocols** only | `storage.sqlite`, `holodeck_control_plane`, SQLite/HTTP types |
| Storage | `holodeck_governance.storage` | `domain`; stdlib `sqlite3` inside `storage.sqlite` only | `application`, `holodeck_control_plane` HTTP/MCP modules |
| Adapters | `holodeck_control_plane` | `holodeck_governance.application` / selected domain types | Must not write M1 governed tables except via application commands |

## Migration seams

| Seam | Purpose | Owner |
| --- | --- | --- |
| `holodeck_governance.storage.legacy_seam` | Map M0 workspace/task/run/claim rows into tenant-bound import facts | M1-006, M1-023 |
| Thin-slice tables (`missions`, `mission_evidence`, `acceptance_decisions`, `curator_proposals`, `workspace_sources`) | Additive `legacy_import` only; unsupported as M1 Approval/Evidence/Decision/Policy | M1-006, M1-023 |
| Control-plane HTTP/CLI/MCP | Retain current behavior; later thin translators to commands | M1-023 parity |

## Record-family ownership

See vocabulary table in package module. Each family has one domain module, one
persistence contract (repository protocol), and one implementing packet.
