"""SQLite persistence for immutable factual code-graph snapshots (M2-021)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from holodeck_governance.domain.errors import (
    ContentionError,
    CrossTenantAccessError,
    MalformedCommandError,
    NotFoundGovernanceError,
    RevisionImmutableError,
)
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    EntityKind,
    ExtractionDiagnostic,
    ExtractionLimits,
    ExtractionRunStatus,
    ObservationMethod,
    RelationKind,
    RepositoryExtractionRun,
    RepositoryGraphSnapshot,
    SnapshotStatus,
    SourceSpan,
    assert_relation_endpoints_resolve,
    assert_snapshot_counts_match,
    code_graph_error,
)


def _insert_immutable(conn: sqlite3.Connection, sql: str, params: tuple) -> None:
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        raise RevisionImmutableError(
            "code-graph record already exists and cannot be overwritten"
        ) from exc


def _json_list(values: tuple[str, ...]) -> str:
    return json.dumps(list(values))


def _read_list(raw: object) -> tuple[str, ...]:
    return tuple(json.loads(str(raw)))


def _limits_json(limits: ExtractionLimits) -> str:
    return json.dumps(
        {
            "max_files": limits.max_files,
            "max_file_bytes": limits.max_file_bytes,
            "max_entities": limits.max_entities,
            "max_relations": limits.max_relations,
            "max_seconds": limits.max_seconds,
        }
    )


def _limits_from_json(raw: object) -> ExtractionLimits:
    payload = json.loads(str(raw))
    return ExtractionLimits(
        max_files=payload.get("max_files"),
        max_file_bytes=payload.get("max_file_bytes"),
        max_entities=payload.get("max_entities"),
        max_relations=payload.get("max_relations"),
        max_seconds=payload.get("max_seconds"),
    )


class SqliteCodeGraphRepository:
    """Tenant-safe immutable store for factual code-graph snapshots."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def _commit_write(self) -> None:
        self._conn.commit()

    def save_building_snapshot(self, snapshot: RepositoryGraphSnapshot) -> None:
        if snapshot.status is not SnapshotStatus.BUILDING:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "new snapshots must start in building status",
            )
        self._insert_snapshot(snapshot)
        self._commit_write()

    def save_extraction_run(self, run: RepositoryExtractionRun) -> None:
        snapshot = self.get_snapshot(run.snapshot_id)
        if snapshot is None:
            raise NotFoundGovernanceError(f"unknown snapshot {run.snapshot_id}")
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_code_graph_extraction_runs(
                extraction_run_id, snapshot_id, tenant_id, provider_key,
                provider_version, provider_schema_version, configuration_hash,
                requested_revision, actual_revision, started_at, completed_at,
                status, created_by_actor_id, limits_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.extraction_run_id,
                run.snapshot_id,
                snapshot.tenant_id,
                run.provider_key,
                run.provider_version,
                run.provider_schema_version,
                run.configuration_hash,
                run.requested_revision,
                run.actual_revision,
                run.started_at.isoformat(),
                None if run.completed_at is None else run.completed_at.isoformat(),
                run.status.value,
                run.created_by_actor_id,
                _limits_json(run.limits),
                run.schema_version,
            ),
        )
        for index, diagnostic in enumerate(run.diagnostics):
            _insert_immutable(
                self._conn,
                """
                INSERT INTO gov_code_graph_extraction_diagnostics(
                    diagnostic_id, extraction_run_id, tenant_id, code, message,
                    repository_relative_path, sequence_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_uuidv7(),
                    run.extraction_run_id,
                    snapshot.tenant_id,
                    diagnostic.code,
                    diagnostic.message,
                    diagnostic.repository_relative_path,
                    index,
                ),
            )
        self._commit_write()

    def insert_entity_fact(self, entity: CodeEntityFact) -> None:
        span = entity.span
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_code_entity_facts(
                entity_fact_id, tenant_id, workspace_object_id,
                repository_binding_id, entity_key, entity_kind, language,
                qualified_name, repository_relative_path, start_line, start_column,
                end_line, end_column, source_id, source_observation_id,
                content_hash, observation_method, extractor_native_id, created_at,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity.entity_fact_id,
                entity.tenant_id,
                entity.workspace_object_id,
                entity.repository_binding_id,
                entity.entity_key,
                entity.entity_kind.value,
                entity.language,
                entity.qualified_name,
                entity.repository_relative_path,
                None if span is None else span.start_line,
                None if span is None else span.start_column,
                None if span is None else span.end_line,
                None if span is None else span.end_column,
                entity.source_id,
                entity.source_observation_id,
                entity.content_hash,
                entity.observation_method.value,
                entity.extractor_native_id,
                entity.created_at.isoformat(),
                entity.schema_version,
            ),
        )
        self._commit_write()

    def insert_relation_fact(self, relation: CodeRelationFact) -> None:
        span = relation.evidence_span
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_code_relation_facts(
                relation_fact_id, tenant_id, workspace_object_id,
                repository_binding_id, relation_kind, source_entity_fact_id,
                target_entity_fact_id, evidence_source_id, evidence_observation_id,
                start_line, start_column, end_line, end_column, observation_method,
                confidence, diagnostic, qualifiers_json, created_at, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation.relation_fact_id,
                relation.tenant_id,
                relation.workspace_object_id,
                relation.repository_binding_id,
                relation.relation_kind.value,
                relation.source_entity_fact_id,
                relation.target_entity_fact_id,
                relation.evidence_source_id,
                relation.evidence_observation_id,
                None if span is None else span.start_line,
                None if span is None else span.start_column,
                None if span is None else span.end_line,
                None if span is None else span.end_column,
                relation.observation_method.value,
                relation.confidence,
                relation.diagnostic,
                _json_list(relation.qualifiers),
                relation.created_at.isoformat(),
                relation.schema_version,
            ),
        )
        self._commit_write()

    def add_snapshot_entity_memberships(
        self, *, snapshot_id: str, tenant_id: str, entity_fact_ids: tuple[str, ...]
    ) -> None:
        for entity_fact_id in entity_fact_ids:
            _insert_immutable(
                self._conn,
                """
                INSERT INTO gov_code_graph_snapshot_entities(
                    snapshot_id, entity_fact_id, tenant_id
                ) VALUES (?, ?, ?)
                """,
                (snapshot_id, entity_fact_id, tenant_id),
            )
        self._commit_write()

    def add_snapshot_relation_memberships(
        self, *, snapshot_id: str, tenant_id: str, relation_fact_ids: tuple[str, ...]
    ) -> None:
        for relation_fact_id in relation_fact_ids:
            _insert_immutable(
                self._conn,
                """
                INSERT INTO gov_code_graph_snapshot_relations(
                    snapshot_id, relation_fact_id, tenant_id
                ) VALUES (?, ?, ?)
                """,
                (snapshot_id, relation_fact_id, tenant_id),
            )
        self._commit_write()

    def mark_snapshot_failed(
        self, snapshot_id: str, *, tenant_id: str, coverage_notes: tuple[str, ...]
    ) -> RepositoryGraphSnapshot:
        snapshot = self.require_snapshot(snapshot_id, tenant_id=tenant_id)
        if snapshot.status is not SnapshotStatus.BUILDING:
            raise MalformedCommandError("only building snapshots can fail")
        self._conn.execute(
            """
            UPDATE gov_code_graph_snapshots
            SET status = ?, coverage_status = ?, coverage_notes_json = ?
            WHERE snapshot_id = ? AND tenant_id = ? AND status = ?
            """,
            (
                SnapshotStatus.FAILED.value,
                CoverageStatus.PARTIAL.value,
                _json_list(coverage_notes),
                snapshot_id,
                tenant_id,
                SnapshotStatus.BUILDING.value,
            ),
        )
        self._commit_write()
        return self.require_snapshot(snapshot_id, tenant_id=tenant_id)

    def activate_snapshot(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        activated_at: datetime,
    ) -> RepositoryGraphSnapshot:
        """Atomically activate a building snapshot; supersede any prior active."""

        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            snapshot = self.require_snapshot(snapshot_id, tenant_id=tenant_id)
            if snapshot.status is not SnapshotStatus.BUILDING:
                raise MalformedCommandError("only building snapshots can activate")
            run = self.get_extraction_run(snapshot.extraction_run_id)
            if run is None:
                raise NotFoundGovernanceError("extraction run missing for snapshot")
            if run.requested_revision != run.actual_revision:
                raise code_graph_error(
                    CodeGraphReason.REVISION_MISMATCH,
                    "requested and actual revisions must match before activation",
                )
            if run.status not in (
                ExtractionRunStatus.SUCCEEDED,
                ExtractionRunStatus.PARTIAL,
            ):
                raise MalformedCommandError(
                    "extraction run must succeed or be partial before activation"
                )
            entities = self.list_snapshot_entities(snapshot_id, tenant_id=tenant_id)
            relations = self.list_snapshot_relations(snapshot_id, tenant_id=tenant_id)
            assert_relation_endpoints_resolve(entities=entities, relations=relations)
            assert_snapshot_counts_match(
                snapshot, entities=entities, relations=relations
            )

            self._conn.execute(
                """
                UPDATE gov_code_graph_snapshots
                SET status = ?
                WHERE tenant_id = ?
                  AND workspace_object_id = ?
                  AND repository_binding_id = ?
                  AND status = ?
                  AND snapshot_id != ?
                """,
                (
                    SnapshotStatus.SUPERSEDED.value,
                    tenant_id,
                    snapshot.workspace_object_id,
                    snapshot.repository_binding_id,
                    SnapshotStatus.ACTIVE.value,
                    snapshot_id,
                ),
            )
            cursor = self._conn.execute(
                """
                UPDATE gov_code_graph_snapshots
                SET status = ?, activated_at = ?, coverage_status = ?
                WHERE snapshot_id = ?
                  AND tenant_id = ?
                  AND status = ?
                """,
                (
                    SnapshotStatus.ACTIVE.value,
                    activated_at.isoformat(),
                    snapshot.coverage_status.value
                    if snapshot.coverage_status is not CoverageStatus.UNKNOWN
                    else CoverageStatus.COMPLETE.value,
                    snapshot_id,
                    tenant_id,
                    SnapshotStatus.BUILDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ContentionError("snapshot activation lost a race")
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = previous
        return self.require_snapshot(snapshot_id, tenant_id=tenant_id)

    def get_snapshot(self, snapshot_id: str) -> RepositoryGraphSnapshot | None:
        row = self._conn.execute(
            "SELECT * FROM gov_code_graph_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return None if row is None else self._snapshot_from_row(row)

    def require_snapshot(
        self, snapshot_id: str, *, tenant_id: str
    ) -> RepositoryGraphSnapshot:
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise NotFoundGovernanceError(f"unknown snapshot {snapshot_id}")
        if snapshot.tenant_id != tenant_id:
            raise CrossTenantAccessError("snapshot tenant mismatch")
        return snapshot

    def get_active_snapshot(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        repository_binding_id: str,
    ) -> RepositoryGraphSnapshot | None:
        row = self._conn.execute(
            """
            SELECT * FROM gov_code_graph_snapshots
            WHERE tenant_id = ?
              AND workspace_object_id = ?
              AND repository_binding_id = ?
              AND status = ?
            """,
            (
                tenant_id,
                workspace_object_id,
                repository_binding_id,
                SnapshotStatus.ACTIVE.value,
            ),
        ).fetchone()
        return None if row is None else self._snapshot_from_row(row)

    def get_extraction_run(
        self, extraction_run_id: str
    ) -> RepositoryExtractionRun | None:
        row = self._conn.execute(
            "SELECT * FROM gov_code_graph_extraction_runs WHERE extraction_run_id = ?",
            (extraction_run_id,),
        ).fetchone()
        if row is None:
            return None
        diagnostics = self._diagnostics_for_run(extraction_run_id)
        return RepositoryExtractionRun(
            extraction_run_id=str(row["extraction_run_id"]),
            snapshot_id=str(row["snapshot_id"]),
            provider_key=str(row["provider_key"]),
            provider_version=str(row["provider_version"]),
            provider_schema_version=str(row["provider_schema_version"]),
            configuration_hash=str(row["configuration_hash"]),
            requested_revision=str(row["requested_revision"]),
            actual_revision=str(row["actual_revision"]),
            started_at=datetime.fromisoformat(str(row["started_at"])),
            status=ExtractionRunStatus(str(row["status"])),
            created_by_actor_id=str(row["created_by_actor_id"]),
            completed_at=(
                None
                if row["completed_at"] is None
                else datetime.fromisoformat(str(row["completed_at"]))
            ),
            diagnostics=diagnostics,
            limits=_limits_from_json(row["limits_json"]),
            schema_version=str(row["schema_version"]),
        )

    def list_snapshot_entities(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeEntityFact, ...]:
        rows = self._conn.execute(
            """
            SELECT f.* FROM gov_code_entity_facts f
            JOIN gov_code_graph_snapshot_entities m
              ON m.entity_fact_id = f.entity_fact_id
            WHERE m.snapshot_id = ? AND m.tenant_id = ?
            ORDER BY f.entity_key
            """,
            (snapshot_id, tenant_id),
        ).fetchall()
        return tuple(self._entity_from_row(row) for row in rows)

    def list_snapshot_relations(
        self, snapshot_id: str, *, tenant_id: str
    ) -> tuple[CodeRelationFact, ...]:
        rows = self._conn.execute(
            """
            SELECT f.* FROM gov_code_relation_facts f
            JOIN gov_code_graph_snapshot_relations m
              ON m.relation_fact_id = f.relation_fact_id
            WHERE m.snapshot_id = ? AND m.tenant_id = ?
            ORDER BY f.relation_kind, f.relation_fact_id
            """,
            (snapshot_id, tenant_id),
        ).fetchall()
        return tuple(self._relation_from_row(row) for row in rows)

    def get_entity_fact(self, entity_fact_id: str) -> CodeEntityFact | None:
        row = self._conn.execute(
            "SELECT * FROM gov_code_entity_facts WHERE entity_fact_id = ?",
            (entity_fact_id,),
        ).fetchone()
        return None if row is None else self._entity_from_row(row)

    def _insert_snapshot(self, snapshot: RepositoryGraphSnapshot) -> None:
        _insert_immutable(
            self._conn,
            """
            INSERT INTO gov_code_graph_snapshots(
                snapshot_id, tenant_id, workspace_object_id, repository_binding_id,
                repository_revision, status, extraction_run_id, coverage_status,
                coverage_notes_json, entity_count, relation_count,
                created_by_actor_id, created_at, base_snapshot_id, activated_at,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.tenant_id,
                snapshot.workspace_object_id,
                snapshot.repository_binding_id,
                snapshot.repository_revision,
                snapshot.status.value,
                snapshot.extraction_run_id,
                snapshot.coverage_status.value,
                _json_list(snapshot.coverage_notes),
                snapshot.entity_count,
                snapshot.relation_count,
                snapshot.created_by_actor_id,
                snapshot.created_at.isoformat(),
                snapshot.base_snapshot_id,
                None
                if snapshot.activated_at is None
                else snapshot.activated_at.isoformat(),
                snapshot.schema_version,
            ),
        )

    def _diagnostics_for_run(
        self, extraction_run_id: str
    ) -> tuple[ExtractionDiagnostic, ...]:
        rows = self._conn.execute(
            """
            SELECT * FROM gov_code_graph_extraction_diagnostics
            WHERE extraction_run_id = ?
            ORDER BY sequence_no
            """,
            (extraction_run_id,),
        ).fetchall()
        return tuple(
            ExtractionDiagnostic(
                code=str(row["code"]),
                message=str(row["message"]),
                repository_relative_path=(
                    None
                    if row["repository_relative_path"] is None
                    else str(row["repository_relative_path"])
                ),
            )
            for row in rows
        )

    @staticmethod
    def _snapshot_from_row(row: sqlite3.Row) -> RepositoryGraphSnapshot:
        return RepositoryGraphSnapshot(
            snapshot_id=str(row["snapshot_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            repository_binding_id=str(row["repository_binding_id"]),
            repository_revision=str(row["repository_revision"]),
            status=SnapshotStatus(str(row["status"])),
            extraction_run_id=str(row["extraction_run_id"]),
            coverage_status=CoverageStatus(str(row["coverage_status"])),
            entity_count=int(row["entity_count"]),
            relation_count=int(row["relation_count"]),
            created_by_actor_id=str(row["created_by_actor_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            base_snapshot_id=(
                None
                if row["base_snapshot_id"] is None
                else str(row["base_snapshot_id"])
            ),
            coverage_notes=_read_list(row["coverage_notes_json"]),
            activated_at=(
                None
                if row["activated_at"] is None
                else datetime.fromisoformat(str(row["activated_at"]))
            ),
            schema_version=str(row["schema_version"]),
        )

    @staticmethod
    def _span_from_row(row: sqlite3.Row) -> SourceSpan | None:
        if row["start_line"] is None:
            return None
        return SourceSpan(
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            start_column=(
                None if row["start_column"] is None else int(row["start_column"])
            ),
            end_column=None if row["end_column"] is None else int(row["end_column"]),
        )

    def _entity_from_row(self, row: sqlite3.Row) -> CodeEntityFact:
        return CodeEntityFact(
            entity_fact_id=str(row["entity_fact_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            repository_binding_id=str(row["repository_binding_id"]),
            entity_key=str(row["entity_key"]),
            entity_kind=EntityKind(str(row["entity_kind"])),
            repository_relative_path=str(row["repository_relative_path"]),
            source_id=str(row["source_id"]),
            source_observation_id=str(row["source_observation_id"]),
            observation_method=ObservationMethod(str(row["observation_method"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            language=None if row["language"] is None else str(row["language"]),
            qualified_name=(
                None if row["qualified_name"] is None else str(row["qualified_name"])
            ),
            span=self._span_from_row(row),
            content_hash=(
                None if row["content_hash"] is None else str(row["content_hash"])
            ),
            extractor_native_id=(
                None
                if row["extractor_native_id"] is None
                else str(row["extractor_native_id"])
            ),
            schema_version=str(row["schema_version"]),
        )

    def _relation_from_row(self, row: sqlite3.Row) -> CodeRelationFact:
        return CodeRelationFact(
            relation_fact_id=str(row["relation_fact_id"]),
            tenant_id=str(row["tenant_id"]),
            workspace_object_id=str(row["workspace_object_id"]),
            repository_binding_id=str(row["repository_binding_id"]),
            relation_kind=RelationKind(str(row["relation_kind"])),
            source_entity_fact_id=str(row["source_entity_fact_id"]),
            target_entity_fact_id=str(row["target_entity_fact_id"]),
            evidence_source_id=str(row["evidence_source_id"]),
            evidence_observation_id=str(row["evidence_observation_id"]),
            observation_method=ObservationMethod(str(row["observation_method"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            evidence_span=self._span_from_row(row),
            confidence=(
                None if row["confidence"] is None else float(row["confidence"])
            ),
            qualifiers=_read_list(row["qualifiers_json"]),
            diagnostic=None if row["diagnostic"] is None else str(row["diagnostic"]),
            schema_version=str(row["schema_version"]),
        )
