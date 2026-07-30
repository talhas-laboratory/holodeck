"""Migration 23: immutable factual code-graph persistence."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v13 import install_tenant_row_ref_triggers
from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v9 import install_tenant_actor_triggers

CODE_GRAPH_TABLES: tuple[str, ...] = (
    "gov_code_graph_snapshots",
    "gov_code_graph_extraction_runs",
    "gov_code_graph_extraction_diagnostics",
    "gov_code_entity_facts",
    "gov_code_relation_facts",
    "gov_code_graph_snapshot_entities",
    "gov_code_graph_snapshot_relations",
)


def upgrade_code_graph_persistence(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE gov_code_graph_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            repository_binding_id TEXT NOT NULL
                REFERENCES gov_repository_bindings(binding_id),
            repository_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            extraction_run_id TEXT NOT NULL,
            coverage_status TEXT NOT NULL,
            coverage_notes_json TEXT NOT NULL,
            entity_count INTEGER NOT NULL,
            relation_count INTEGER NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            base_snapshot_id TEXT REFERENCES gov_code_graph_snapshots(snapshot_id),
            activated_at TEXT,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX gov_code_graph_snapshots_one_active
        ON gov_code_graph_snapshots(
            tenant_id, workspace_object_id, repository_binding_id
        )
        WHERE status = 'active'
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_snapshots_binding
        ON gov_code_graph_snapshots(
            tenant_id, workspace_object_id, repository_binding_id, status
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_snapshots_revision
        ON gov_code_graph_snapshots(
            tenant_id, repository_binding_id, repository_revision
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_graph_extraction_runs (
            extraction_run_id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL
                REFERENCES gov_code_graph_snapshots(snapshot_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            provider_key TEXT NOT NULL,
            provider_version TEXT NOT NULL,
            provider_schema_version TEXT NOT NULL,
            configuration_hash TEXT NOT NULL,
            requested_revision TEXT NOT NULL,
            actual_revision TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            created_by_actor_id TEXT NOT NULL,
            limits_json TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_extraction_runs_snapshot
        ON gov_code_graph_extraction_runs(snapshot_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_graph_extraction_diagnostics (
            diagnostic_id TEXT PRIMARY KEY,
            extraction_run_id TEXT NOT NULL
                REFERENCES gov_code_graph_extraction_runs(extraction_run_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            code TEXT NOT NULL,
            message TEXT NOT NULL,
            repository_relative_path TEXT,
            sequence_no INTEGER NOT NULL,
            UNIQUE(extraction_run_id, sequence_no)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_entity_facts (
            entity_fact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            repository_binding_id TEXT NOT NULL
                REFERENCES gov_repository_bindings(binding_id),
            entity_key TEXT NOT NULL,
            entity_kind TEXT NOT NULL,
            language TEXT,
            qualified_name TEXT,
            repository_relative_path TEXT NOT NULL,
            start_line INTEGER,
            start_column INTEGER,
            end_line INTEGER,
            end_column INTEGER,
            source_id TEXT NOT NULL REFERENCES gov_workspace_sources(source_id),
            source_observation_id TEXT NOT NULL
                REFERENCES gov_workspace_source_observations(observation_id),
            content_hash TEXT,
            observation_method TEXT NOT NULL,
            extractor_native_id TEXT,
            created_at TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            UNIQUE(
                tenant_id, workspace_object_id, repository_binding_id, entity_key
            )
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_entity_facts_lookup
        ON gov_code_entity_facts(
            tenant_id, workspace_object_id, repository_binding_id,
            entity_kind, repository_relative_path
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_entity_facts_source
        ON gov_code_entity_facts(tenant_id, source_id, source_observation_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_relation_facts (
            relation_fact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            workspace_object_id TEXT NOT NULL REFERENCES gov_objects(object_id),
            repository_binding_id TEXT NOT NULL
                REFERENCES gov_repository_bindings(binding_id),
            relation_kind TEXT NOT NULL,
            source_entity_fact_id TEXT NOT NULL
                REFERENCES gov_code_entity_facts(entity_fact_id),
            target_entity_fact_id TEXT NOT NULL
                REFERENCES gov_code_entity_facts(entity_fact_id),
            evidence_source_id TEXT NOT NULL
                REFERENCES gov_workspace_sources(source_id),
            evidence_observation_id TEXT NOT NULL
                REFERENCES gov_workspace_source_observations(observation_id),
            start_line INTEGER,
            start_column INTEGER,
            end_line INTEGER,
            end_column INTEGER,
            observation_method TEXT NOT NULL,
            confidence REAL,
            diagnostic TEXT,
            qualifiers_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            schema_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_relation_facts_expand
        ON gov_code_relation_facts(
            tenant_id, workspace_object_id, repository_binding_id,
            relation_kind, source_entity_fact_id
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_relation_facts_target
        ON gov_code_relation_facts(
            tenant_id, target_entity_fact_id, relation_kind
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_graph_snapshot_entities (
            snapshot_id TEXT NOT NULL
                REFERENCES gov_code_graph_snapshots(snapshot_id),
            entity_fact_id TEXT NOT NULL
                REFERENCES gov_code_entity_facts(entity_fact_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            PRIMARY KEY (snapshot_id, entity_fact_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_snapshot_entities_fact
        ON gov_code_graph_snapshot_entities(entity_fact_id, snapshot_id)
        """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_graph_snapshot_relations (
            snapshot_id TEXT NOT NULL
                REFERENCES gov_code_graph_snapshots(snapshot_id),
            relation_fact_id TEXT NOT NULL
                REFERENCES gov_code_relation_facts(relation_fact_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            PRIMARY KEY (snapshot_id, relation_fact_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_snapshot_relations_fact
        ON gov_code_graph_snapshot_relations(relation_fact_id, snapshot_id)
        """
    )

    _install_triggers(conn)
    _install_coupling_triggers(conn)


def _install_triggers(conn: sqlite3.Connection) -> None:
    for table in (
        "gov_code_graph_snapshots",
        "gov_code_entity_facts",
        "gov_code_relation_facts",
    ):
        install_tenant_object_triggers(conn, table=table, column="workspace_object_id")
    install_tenant_actor_triggers(
        conn, table="gov_code_graph_snapshots", column="created_by_actor_id"
    )
    install_tenant_actor_triggers(
        conn,
        table="gov_code_graph_extraction_runs",
        column="created_by_actor_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_graph_snapshots",
        column="repository_binding_id",
        ref_table="gov_repository_bindings",
        ref_pk="binding_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_entity_facts",
        column="repository_binding_id",
        ref_table="gov_repository_bindings",
        ref_pk="binding_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_relation_facts",
        column="repository_binding_id",
        ref_table="gov_repository_bindings",
        ref_pk="binding_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_entity_facts",
        column="source_id",
        ref_table="gov_workspace_sources",
        ref_pk="source_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_entity_facts",
        column="source_observation_id",
        ref_table="gov_workspace_source_observations",
        ref_pk="observation_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_relation_facts",
        column="evidence_source_id",
        ref_table="gov_workspace_sources",
        ref_pk="source_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_relation_facts",
        column="evidence_observation_id",
        ref_table="gov_workspace_source_observations",
        ref_pk="observation_id",
    )
    install_tenant_row_ref_triggers(
        conn,
        table="gov_code_graph_extraction_runs",
        column="snapshot_id",
        ref_table="gov_code_graph_snapshots",
        ref_pk="snapshot_id",
    )


def _install_coupling_triggers(conn: sqlite3.Connection) -> None:
    """Reject cross-binding relation endpoints and membership mismatches."""

    for kind, when_extra in (
        ("ins", "BEFORE INSERT ON gov_code_relation_facts"),
        (
            "upd",
            "BEFORE UPDATE OF source_entity_fact_id, target_entity_fact_id, "
            "tenant_id, workspace_object_id, repository_binding_id "
            "ON gov_code_relation_facts",
        ),
    ):
        name = f"gov_code_relation_facts_endpoint_coupling_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_code_entity_facts s
                JOIN gov_code_entity_facts t
                  ON t.entity_fact_id = NEW.target_entity_fact_id
                WHERE s.entity_fact_id = NEW.source_entity_fact_id
                  AND s.tenant_id = NEW.tenant_id
                  AND t.tenant_id = NEW.tenant_id
                  AND s.workspace_object_id = NEW.workspace_object_id
                  AND t.workspace_object_id = NEW.workspace_object_id
                  AND s.repository_binding_id = NEW.repository_binding_id
                  AND t.repository_binding_id = NEW.repository_binding_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'relation endpoints must share tenant/workspace/binding'
                );
            END
            """
        )

    for membership, fact_table, fact_pk in (
        (
            "gov_code_graph_snapshot_entities",
            "gov_code_entity_facts",
            "entity_fact_id",
        ),
        (
            "gov_code_graph_snapshot_relations",
            "gov_code_relation_facts",
            "relation_fact_id",
        ),
    ):
        for kind, when_extra in (
            ("ins", f"BEFORE INSERT ON {membership}"),
            (
                "upd",
                f"BEFORE UPDATE OF snapshot_id, {fact_pk}, tenant_id ON {membership}",
            ),
        ):
            name = f"{membership}_tenant_coupling_{kind}"
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(
                f"""
                CREATE TRIGGER {name}
                {when_extra}
                WHEN NOT EXISTS (
                    SELECT 1 FROM gov_code_graph_snapshots snap
                    JOIN {fact_table} fact
                      ON fact.{fact_pk} = NEW.{fact_pk}
                    WHERE snap.snapshot_id = NEW.snapshot_id
                      AND snap.tenant_id = NEW.tenant_id
                      AND fact.tenant_id = NEW.tenant_id
                      AND snap.workspace_object_id = fact.workspace_object_id
                      AND snap.repository_binding_id = fact.repository_binding_id
                )
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'snapshot membership tenant/workspace/binding mismatch'
                    );
                END
                """
            )
