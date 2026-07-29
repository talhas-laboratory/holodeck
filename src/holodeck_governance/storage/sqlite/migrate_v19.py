"""Migration 19: workspace intelligence persistence tables."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers
from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers


def upgrade_workspace_intelligence(conn: sqlite3.Connection) -> None:
    """Persist model revisions, sources, modules, gaps, decisions, readiness."""

    conn.execute(
        """
        CREATE TABLE gov_workspace_model_revisions (
            model_revision_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            revision INTEGER NOT NULL,
            status TEXT NOT NULL,
            intent_seed_json TEXT NOT NULL,
            sections_json TEXT NOT NULL,
            based_on_revision_id TEXT
                REFERENCES gov_workspace_model_revisions(model_revision_id),
            provenance_reference_ids_json TEXT NOT NULL,
            confidence_summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            approved_at TEXT,
            approved_by_actor_id TEXT,
            schema_version TEXT NOT NULL,
            UNIQUE (tenant_id, workspace_object_id, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_workspace_model_revisions_workspace
        ON gov_workspace_model_revisions(tenant_id, workspace_object_id, revision)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_workspace_sources (
            source_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            source_type TEXT NOT NULL,
            locator TEXT NOT NULL,
            observed_revision TEXT NOT NULL,
            trust_class TEXT NOT NULL,
            owner_actor_id TEXT NOT NULL,
            sensitivity TEXT NOT NULL,
            refresh_policy TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            stale_status TEXT NOT NULL,
            instruction_authority INTEGER NOT NULL,
            content_hash TEXT,
            provenance_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            module_tags_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE (tenant_id, workspace_object_id, locator)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_workspace_sources_workspace
        ON gov_workspace_sources(tenant_id, workspace_object_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_context_items (
            item_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            item_type TEXT NOT NULL,
            statement TEXT NOT NULL,
            trust_class TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            freshness TEXT NOT NULL,
            source_reference_ids_json TEXT NOT NULL,
            confidence REAL,
            applicability TEXT NOT NULL,
            conflicts_with_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            approved_by_actor_id TEXT,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_context_items_workspace
        ON gov_context_items(tenant_id, workspace_object_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_context_modules (
            module_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            module_key TEXT NOT NULL,
            purpose_text TEXT NOT NULL,
            applicability_text TEXT NOT NULL,
            approval_status TEXT NOT NULL,
            freshness TEXT NOT NULL,
            revision INTEGER NOT NULL,
            item_ids_json TEXT NOT NULL,
            source_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            approved_at TEXT,
            approved_by_actor_id TEXT,
            schema_version TEXT NOT NULL,
            UNIQUE (tenant_id, workspace_object_id, module_key, revision)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_context_modules_workspace
        ON gov_context_modules(tenant_id, workspace_object_id, module_key)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_knowledge_gaps (
            gap_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            question TEXT NOT NULL,
            affected_sections_json TEXT NOT NULL,
            impact_text TEXT NOT NULL,
            risk_if_unresolved_text TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_actor_id TEXT,
            resolution_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_knowledge_gaps_workspace
        ON gov_knowledge_gaps(tenant_id, workspace_object_id, status)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_contradictions (
            contradiction_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            claim_reference_ids_json TEXT NOT NULL,
            description TEXT NOT NULL,
            impact_text TEXT NOT NULL,
            status TEXT NOT NULL,
            resolution_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            created_at TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_contradictions_workspace
        ON gov_contradictions(tenant_id, workspace_object_id, status)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_workspace_decisions (
            decision_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            subject_revision_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            rationale TEXT NOT NULL,
            authorized_actor_id TEXT NOT NULL,
            decided_at TEXT NOT NULL,
            signed_source_reference_id TEXT
                REFERENCES gov_external_references(reference_id),
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_workspace_decisions_workspace
        ON gov_workspace_decisions(tenant_id, workspace_object_id, decided_at)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_workspace_readiness_assessments (
            assessment_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            model_revision_id TEXT NOT NULL
                REFERENCES gov_workspace_model_revisions(model_revision_id),
            level TEXT NOT NULL,
            dimensions_checked_json TEXT NOT NULL,
            open_gap_ids_json TEXT NOT NULL,
            policy_basis TEXT NOT NULL,
            evaluator_summary TEXT NOT NULL,
            assessed_at TEXT NOT NULL,
            assessed_by_actor_id TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_workspace_readiness_workspace
        ON gov_workspace_readiness_assessments(
            tenant_id, workspace_object_id, assessed_at
        )
        """
    )

    for table in (
        "gov_workspace_model_revisions",
        "gov_workspace_sources",
        "gov_context_items",
        "gov_context_modules",
        "gov_knowledge_gaps",
        "gov_contradictions",
        "gov_workspace_decisions",
        "gov_workspace_readiness_assessments",
    ):
        install_tenant_object_triggers(
            conn, table=table, column="workspace_object_id"
        )

    for table, column in (
        ("gov_workspace_model_revisions", "created_by_actor_id"),
        ("gov_workspace_sources", "created_by_actor_id"),
        ("gov_workspace_sources", "owner_actor_id"),
        ("gov_context_items", "created_by_actor_id"),
        ("gov_context_modules", "created_by_actor_id"),
        ("gov_knowledge_gaps", "created_by_actor_id"),
        ("gov_contradictions", "created_by_actor_id"),
        ("gov_workspace_decisions", "authorized_actor_id"),
        ("gov_workspace_readiness_assessments", "assessed_by_actor_id"),
    ):
        install_tenant_actor_triggers(conn, table=table, column=column)

    # Nullable actor columns need null-safe tenant coupling (pattern from v17).
    for table, column in (
        ("gov_workspace_model_revisions", "approved_by_actor_id"),
        ("gov_context_items", "approved_by_actor_id"),
        ("gov_context_modules", "approved_by_actor_id"),
        ("gov_knowledge_gaps", "owner_actor_id"),
    ):
        for kind, when_extra in (
            ("ins", f"BEFORE INSERT ON {table}"),
            ("upd", f"BEFORE UPDATE OF {column}, tenant_id ON {table}"),
        ):
            name = f"{table}_tenant_{column}_{kind}"
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(
                f"""
                CREATE TRIGGER {name}
                {when_extra}
                WHEN NEW.{column} IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM gov_actors a
                    WHERE a.actor_id = NEW.{column}
                      AND a.tenant_id = NEW.tenant_id
                )
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cross-tenant authority reference forbidden: {table}.{column}'
                    );
                END
                """
            )

    install_tenant_row_ref_triggers(
        conn,
        table="gov_workspace_sources",
        column="provenance_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_knowledge_gaps",
        column="resolution_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_contradictions",
        column="resolution_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_workspace_decisions",
        column="signed_source_reference_id",
        ref_table="gov_external_references",
        ref_pk="reference_id",
        nullable=True,
    )


WORKSPACE_INTELLIGENCE_TABLES: tuple[str, ...] = (
    "gov_workspace_readiness_assessments",
    "gov_workspace_decisions",
    "gov_contradictions",
    "gov_knowledge_gaps",
    "gov_context_modules",
    "gov_context_items",
    "gov_workspace_sources",
    "gov_workspace_model_revisions",
)
