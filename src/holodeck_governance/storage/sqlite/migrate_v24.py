"""Migration 24: revision-safe fact uniqueness and provenance coupling."""

from __future__ import annotations

import sqlite3

from holodeck_governance.storage.sqlite.migrate_v8 import install_tenant_object_triggers
from holodeck_governance.storage.sqlite.migrate_v13 import (
    install_tenant_row_ref_triggers,
)

CODE_GRAPH_BUILD_CLAIM_TABLES = ("gov_code_graph_build_claims",)


def upgrade_code_graph_foundation_hardening(conn: sqlite3.Connection) -> None:
    """Fix multi-revision fact identity and source/observation coupling.

    - Entity uniqueness includes ``source_observation_id`` so each revision can
      persist its own evidence-backed fact while reusing stable ``entity_key``.
    - Relation uniqueness includes evidence observation for the same reason.
    - Triggers reject facts whose observation does not belong to the paired source.
    - Build claim table supports concurrency-safe idempotency reservation.
    """

    # Rebuild all children first.  SQLite does not permit changing
    # ``foreign_keys`` inside the migration transaction, so a populated v23
    # database cannot safely swap a parent table in place.
    for name in (
        "gov_code_relation_facts_endpoint_coupling_ins",
        "gov_code_relation_facts_endpoint_coupling_upd",
        "gov_code_entity_facts_source_observation_coupling_ins",
        "gov_code_entity_facts_source_observation_coupling_upd",
        "gov_code_relation_facts_evidence_observation_coupling_ins",
        "gov_code_relation_facts_evidence_observation_coupling_upd",
        "gov_code_graph_snapshot_entities_tenant_coupling_ins",
        "gov_code_graph_snapshot_entities_tenant_coupling_upd",
        "gov_code_graph_snapshot_relations_tenant_coupling_ins",
        "gov_code_graph_snapshot_relations_tenant_coupling_upd",
    ):
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")

    conn.execute(
        """
            CREATE TABLE gov_code_entity_facts_v24 (
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
                    tenant_id, workspace_object_id, repository_binding_id,
                    entity_key, source_observation_id
                )
            )
            """
    )
    conn.execute(
        """
            INSERT INTO gov_code_entity_facts_v24
            SELECT * FROM gov_code_entity_facts
            """
    )

    conn.execute(
        """
            CREATE TABLE gov_code_relation_facts_v24 (
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
                schema_version TEXT NOT NULL,
                UNIQUE(
                    tenant_id, workspace_object_id, repository_binding_id,
                    relation_kind, source_entity_fact_id, target_entity_fact_id,
                    evidence_observation_id
                )
            )
            """
    )
    conn.execute(
        """
            INSERT INTO gov_code_relation_facts_v24
            SELECT * FROM gov_code_relation_facts
            """
    )

    conn.execute(
        """
        CREATE TABLE gov_code_graph_snapshot_entities_v24 (
            snapshot_id TEXT NOT NULL
                REFERENCES gov_code_graph_snapshots(snapshot_id),
            entity_fact_id TEXT NOT NULL
                REFERENCES gov_code_entity_facts_v24(entity_fact_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            PRIMARY KEY (snapshot_id, entity_fact_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO gov_code_graph_snapshot_entities_v24
        SELECT * FROM gov_code_graph_snapshot_entities
        """
    )
    conn.execute(
        """
        CREATE TABLE gov_code_graph_snapshot_relations_v24 (
            snapshot_id TEXT NOT NULL
                REFERENCES gov_code_graph_snapshots(snapshot_id),
            relation_fact_id TEXT NOT NULL
                REFERENCES gov_code_relation_facts_v24(relation_fact_id),
            tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
            PRIMARY KEY (snapshot_id, relation_fact_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO gov_code_graph_snapshot_relations_v24
        SELECT * FROM gov_code_graph_snapshot_relations
        """
    )

    # Old membership tables are the FK children of relation/entity facts.
    conn.execute("DROP TABLE gov_code_graph_snapshot_relations")
    conn.execute("DROP TABLE gov_code_graph_snapshot_entities")
    conn.execute("DROP TABLE gov_code_relation_facts")
    conn.execute("DROP TABLE gov_code_entity_facts")
    conn.execute(
        "ALTER TABLE gov_code_entity_facts_v24 RENAME TO gov_code_entity_facts"
    )
    conn.execute(
        "ALTER TABLE gov_code_relation_facts_v24 RENAME TO gov_code_relation_facts"
    )
    conn.execute(
        "ALTER TABLE gov_code_graph_snapshot_entities_v24 "
        "RENAME TO gov_code_graph_snapshot_entities"
    )
    conn.execute(
        "ALTER TABLE gov_code_graph_snapshot_relations_v24 "
        "RENAME TO gov_code_graph_snapshot_relations"
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
        CREATE INDEX gov_code_graph_snapshot_entities_fact
        ON gov_code_graph_snapshot_entities(entity_fact_id, snapshot_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX gov_code_graph_snapshot_relations_fact
        ON gov_code_graph_snapshot_relations(relation_fact_id, snapshot_id)
        """
    )

    conn.execute(
        """
            CREATE TABLE gov_code_graph_build_claims (
                tenant_id TEXT NOT NULL REFERENCES gov_tenants(tenant_id),
                idempotency_key TEXT NOT NULL,
                semantic_hash TEXT NOT NULL,
                command_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, idempotency_key)
            )
            """
    )

    _install_source_observation_coupling(conn)
    _reinstall_endpoint_coupling(conn)
    _reinstall_membership_coupling(conn)
    _reinstall_tenant_ref_triggers(conn)


def _reinstall_tenant_ref_triggers(conn: sqlite3.Connection) -> None:
    for table in ("gov_code_entity_facts", "gov_code_relation_facts"):
        install_tenant_object_triggers(conn, table=table, column="workspace_object_id")
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


def _install_source_observation_coupling(conn: sqlite3.Connection) -> None:
    for kind, when_extra in (
        ("ins", "BEFORE INSERT ON gov_code_entity_facts"),
        (
            "upd",
            "BEFORE UPDATE OF source_id, source_observation_id "
            "ON gov_code_entity_facts",
        ),
    ):
        name = f"gov_code_entity_facts_source_observation_coupling_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_workspace_source_observations o
                WHERE o.observation_id = NEW.source_observation_id
                  AND o.source_id = NEW.source_id
                  AND o.tenant_id = NEW.tenant_id
                  AND o.workspace_object_id = NEW.workspace_object_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'entity source_observation_id must belong to source_id'
                );
            END
            """
        )

    for kind, when_extra in (
        ("ins", "BEFORE INSERT ON gov_code_relation_facts"),
        (
            "upd",
            "BEFORE UPDATE OF evidence_source_id, evidence_observation_id "
            "ON gov_code_relation_facts",
        ),
    ):
        name = f"gov_code_relation_facts_evidence_observation_coupling_{kind}"
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            {when_extra}
            WHEN NOT EXISTS (
                SELECT 1 FROM gov_workspace_source_observations o
                WHERE o.observation_id = NEW.evidence_observation_id
                  AND o.source_id = NEW.evidence_source_id
                  AND o.tenant_id = NEW.tenant_id
                  AND o.workspace_object_id = NEW.workspace_object_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'relation evidence_observation_id must belong to evidence_source_id'
                );
            END
            """
        )


def _reinstall_endpoint_coupling(conn: sqlite3.Connection) -> None:
    """Recreate relation endpoint coupling after table rebuild."""

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


def _reinstall_membership_coupling(conn: sqlite3.Connection) -> None:
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
