"""SQLite persistence for immutable factual code-graph snapshots (M2-021)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Callable

from holodeck_governance.domain.errors import (
    ContentionError,
    CrossTenantAccessError,
    IdempotencyConflictError,
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


def _insert_ignore_existing(conn: sqlite3.Connection, sql: str, params: tuple) -> bool:
    """Insert a row; return False when the primary key already exists."""

    try:
        conn.execute(sql, params)
        return True
    except sqlite3.IntegrityError:
        return False


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


def _sql_in_placeholders(count: int) -> str:
    return ",".join("?" * count)


# Stay under common SQLITE_MAX_VARIABLE_NUMBER builds (often 999).
# either_entity_fact_ids doubles placeholders, so chunk that list smaller.
SQL_IN_CHUNK_SIZE = 400
SQL_IN_EITHER_CHUNK_SIZE = 200


def _escape_like(value: str) -> str:
    """Escape ``\\``, ``%``, and ``_`` for SQLite LIKE with ``ESCAPE '\\'``."""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _chunked(values: tuple[str, ...] | list[str], size: int) -> list[tuple[str, ...]]:
    if not values:
        return []
    return [tuple(values[i : i + size]) for i in range(0, len(values), size)]


class SqliteCodeGraphRepository:
    """Tenant-safe immutable store for factual code-graph snapshots."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        # Optional read accounting for storage-bounded query tests.
        self.entities_rows_fetched = 0
        self.relations_rows_fetched = 0

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
        self._insert_extraction_run(run, tenant_id=snapshot.tenant_id)
        self._commit_write()

    def insert_entity_fact(self, entity: CodeEntityFact) -> None:
        self._insert_entity_fact_row(entity)
        self._commit_write()

    def insert_relation_fact(self, relation: CodeRelationFact) -> None:
        self._insert_relation_fact_row(relation)
        self._commit_write()

    def _insert_entity_fact_row(self, entity: CodeEntityFact) -> None:
        existing = self.get_entity_fact(entity.entity_fact_id)
        if existing is not None:
            if (
                existing.entity_key != entity.entity_key
                or existing.source_observation_id != entity.source_observation_id
            ):
                raise RevisionImmutableError(
                    "code-graph entity fact conflicts with an existing row"
                )
            return
        self._require_observation_belongs_to_source(
            tenant_id=entity.tenant_id,
            workspace_object_id=entity.workspace_object_id,
            source_id=entity.source_id,
            observation_id=entity.source_observation_id,
            kind="entity",
        )
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

    def _insert_relation_fact_row(self, relation: CodeRelationFact) -> None:
        existing = self.get_relation_fact(relation.relation_fact_id)
        if existing is not None:
            if (
                existing.relation_kind != relation.relation_kind
                or existing.evidence_observation_id != relation.evidence_observation_id
            ):
                raise RevisionImmutableError(
                    "code-graph relation fact conflicts with an existing row"
                )
            return
        self._require_observation_belongs_to_source(
            tenant_id=relation.tenant_id,
            workspace_object_id=relation.workspace_object_id,
            source_id=relation.evidence_source_id,
            observation_id=relation.evidence_observation_id,
            kind="relation",
        )
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

    def _require_observation_belongs_to_source(
        self,
        *,
        tenant_id: str,
        workspace_object_id: str,
        source_id: str,
        observation_id: str,
        kind: str,
    ) -> None:
        row = self._conn.execute(
            """
            SELECT 1 FROM gov_workspace_source_observations
            WHERE observation_id = ?
              AND source_id = ?
              AND tenant_id = ?
              AND workspace_object_id = ?
            """,
            (observation_id, source_id, tenant_id, workspace_object_id),
        ).fetchone()
        if row is None:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                f"{kind} observation {observation_id} does not belong to "
                f"source {source_id}",
            )

    def _insert_extraction_run(
        self, run: RepositoryExtractionRun, *, tenant_id: str
    ) -> None:
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
                tenant_id,
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
                    tenant_id,
                    diagnostic.code,
                    diagnostic.message,
                    diagnostic.repository_relative_path,
                    index,
                ),
            )

    def persist_building_graph(
        self,
        *,
        snapshot: RepositoryGraphSnapshot,
        run: RepositoryExtractionRun,
        entities: tuple[CodeEntityFact, ...],
        relations: tuple[CodeRelationFact, ...],
    ) -> None:
        """Persist snapshot, run, facts, and memberships in one transaction."""

        if snapshot.status is not SnapshotStatus.BUILDING:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "new snapshots must start in building status",
            )
        assert_relation_endpoints_resolve(entities=entities, relations=relations)
        assert_snapshot_counts_match(snapshot, entities=entities, relations=relations)

        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._insert_snapshot(snapshot)
            self._insert_extraction_run(run, tenant_id=snapshot.tenant_id)
            for entity in entities:
                self._insert_entity_fact_row(entity)
            for relation in relations:
                self._insert_relation_fact_row(relation)
            for entity in entities:
                _insert_immutable(
                    self._conn,
                    """
                    INSERT INTO gov_code_graph_snapshot_entities(
                        snapshot_id, entity_fact_id, tenant_id
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        entity.entity_fact_id,
                        snapshot.tenant_id,
                    ),
                )
            for relation in relations:
                _insert_immutable(
                    self._conn,
                    """
                    INSERT INTO gov_code_graph_snapshot_relations(
                        snapshot_id, relation_fact_id, tenant_id
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        relation.relation_fact_id,
                        snapshot.tenant_id,
                    ),
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = previous

    def claim_build_idempotency(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        semantic_hash: str,
        command_id: str,
        created_at: datetime,
        lease_seconds: int,
    ) -> str:
        """Reserve an idempotency key before extraction (concurrency-safe).

        Returns ``\"claimed\"`` when this caller owns the key, or
        ``\"already_complete\"`` when a matching receipt already exists.
        Raises ``IdempotencyConflictError`` on fingerprint mismatch and
        ``ContentionError`` when another non-expired build holds the claim.
        """

        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            receipt = self._conn.execute(
                """
                SELECT semantic_hash FROM gov_command_receipts
                WHERE tenant_id = ? AND idempotency_key = ?
                """,
                (tenant_id, idempotency_key),
            ).fetchone()
            if receipt is not None:
                if str(receipt["semantic_hash"]) != semantic_hash:
                    self._conn.execute("ROLLBACK")
                    raise IdempotencyConflictError(
                        "idempotency key was reused with different graph-build inputs"
                    )
                self._conn.execute("COMMIT")
                return "already_complete"
            try:
                self._conn.execute(
                    """
                    INSERT INTO gov_code_graph_build_claims(
                        tenant_id, idempotency_key, semantic_hash,
                        command_id, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        idempotency_key,
                        semantic_hash,
                        command_id,
                        created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                row = self._conn.execute(
                    """
                    SELECT semantic_hash, created_at FROM gov_code_graph_build_claims
                    WHERE tenant_id = ? AND idempotency_key = ?
                    """,
                    (tenant_id, idempotency_key),
                ).fetchone()
                if row is not None and str(row["semantic_hash"]) != semantic_hash:
                    self._conn.execute("ROLLBACK")
                    raise IdempotencyConflictError(
                        "idempotency key was reused with different graph-build inputs"
                    ) from exc
                if row is not None:
                    claimed_at = datetime.fromisoformat(str(row["created_at"]))
                    if claimed_at <= created_at - timedelta(seconds=lease_seconds):
                        self._conn.execute(
                            """
                            DELETE FROM gov_code_graph_build_claims
                            WHERE tenant_id = ? AND idempotency_key = ?
                            """,
                            (tenant_id, idempotency_key),
                        )
                        self._conn.execute(
                            """
                            INSERT INTO gov_code_graph_build_claims(
                                tenant_id, idempotency_key, semantic_hash,
                                command_id, created_at
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                tenant_id,
                                idempotency_key,
                                semantic_hash,
                                command_id,
                                created_at.isoformat(),
                            ),
                        )
                        self._conn.execute("COMMIT")
                        return "claimed"
                self._conn.execute("ROLLBACK")
                raise ContentionError(
                    "graph build idempotency key is already claimed"
                ) from exc
            self._conn.execute("COMMIT")
            return "claimed"
        except (IdempotencyConflictError, ContentionError):
            raise
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = previous

    def release_build_idempotency_claim(
        self, *, tenant_id: str, idempotency_key: str
    ) -> None:
        self._conn.execute(
            """
            DELETE FROM gov_code_graph_build_claims
            WHERE tenant_id = ? AND idempotency_key = ?
            """,
            (tenant_id, idempotency_key),
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
        expected_active_snapshot_id: str | None = None,
        expect_no_active_snapshot: bool = False,
    ) -> RepositoryGraphSnapshot:
        """Atomically activate a building snapshot; supersede any prior active.

        Activation always applies an explicit CAS precondition:
        - ``expect_no_active_snapshot=True`` requires no current active snapshot
        - otherwise ``expected_active_snapshot_id`` must match the current active

        ``None`` never means “skip comparison.”
        """

        return self.run_activation_unit_of_work(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            activated_at=activated_at,
            expected_active_snapshot_id=expected_active_snapshot_id,
            expect_no_active_snapshot=expect_no_active_snapshot,
            steps=(),
        )

    def run_activation_unit_of_work(
        self,
        *,
        snapshot_id: str,
        tenant_id: str,
        activated_at: datetime,
        expected_active_snapshot_id: str | None,
        expect_no_active_snapshot: bool,
        steps: tuple[tuple[str, Callable[[], None]], ...] = (),
        fault_before: str | None = None,
    ) -> RepositoryGraphSnapshot:
        """Activate under one BEGIN IMMEDIATE with optional post-activate steps.

        All steps share the transaction. Any failure rolls back activation,
        source pointer updates, events, and receipts written by the steps.
        """

        if expect_no_active_snapshot and expected_active_snapshot_id is not None:
            raise MalformedCommandError(
                "expect_no_active_snapshot cannot be combined with "
                "expected_active_snapshot_id"
            )
        if not expect_no_active_snapshot and expected_active_snapshot_id is None:
            raise MalformedCommandError(
                "activation requires expected_active_snapshot_id or "
                "expect_no_active_snapshot=True"
            )

        previous = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if fault_before == "cas":
                raise RuntimeError("injected fault before cas")
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
            if run.status is ExtractionRunStatus.FAILED:
                raise MalformedCommandError("failed extraction runs cannot activate")
            if run.status is ExtractionRunStatus.PARTIAL:
                raise code_graph_error(
                    CodeGraphReason.PARTIAL_COVERAGE,
                    "partial extraction runs cannot activate without a policy decision",
                )
            if run.status not in (
                ExtractionRunStatus.SUCCEEDED,
                ExtractionRunStatus.PARTIAL,
            ):
                raise MalformedCommandError(
                    "extraction run must succeed or be partial before activation"
                )
            if snapshot.coverage_status is CoverageStatus.PARTIAL:
                raise code_graph_error(
                    CodeGraphReason.PARTIAL_COVERAGE,
                    "partial snapshots cannot activate without a policy decision",
                )
            entities = self.list_snapshot_entities(snapshot_id, tenant_id=tenant_id)
            relations = self.list_snapshot_relations(snapshot_id, tenant_id=tenant_id)
            assert_relation_endpoints_resolve(entities=entities, relations=relations)
            assert_snapshot_counts_match(
                snapshot, entities=entities, relations=relations
            )

            current_active = self.get_active_snapshot(
                tenant_id=tenant_id,
                workspace_object_id=snapshot.workspace_object_id,
                repository_binding_id=snapshot.repository_binding_id,
            )
            if expect_no_active_snapshot:
                if current_active is not None:
                    raise ContentionError("base_snapshot_not_current")
            elif (
                current_active is None
                or current_active.snapshot_id != expected_active_snapshot_id
            ):
                raise ContentionError("base_snapshot_not_current")

            if fault_before == "activate":
                raise RuntimeError("injected fault before activate")

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

            for name, step in steps:
                if fault_before == name:
                    raise RuntimeError(f"injected fault before {name}")
                step()
                if fault_before == f"after:{name}":
                    raise RuntimeError(f"injected fault after {name}")

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
        self.entities_rows_fetched += len(rows)
        return tuple(self._entity_from_row(row) for row in rows)

    def find_snapshot_entities(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        entity_kind: str | None = None,
        entity_kinds: tuple[str, ...] | None = None,
        language: str | None = None,
        qualified_name: str | None = None,
        qualified_name_exact: bool = False,
        entity_fact_ids: tuple[str, ...] | None = None,
        repository_relative_path: str | None = None,
        path_prefix: str | None = None,
        limit: int | None = None,
    ) -> tuple[CodeEntityFact, ...]:
        """Bounded entity lookup using ``gov_code_entity_facts_lookup`` columns."""

        if entity_fact_ids is not None and not entity_fact_ids:
            return ()
        if entity_kinds is not None and not entity_kinds:
            return ()

        id_chunks: list[tuple[str, ...] | None]
        if entity_fact_ids is None:
            id_chunks = [None]
        else:
            id_chunks = _chunked(entity_fact_ids, SQL_IN_CHUNK_SIZE)

        collected: list[CodeEntityFact] = []
        seen: set[str] = set()
        for id_chunk in id_chunks:
            remaining = None if limit is None else max(limit - len(collected), 0)
            if limit is not None and remaining == 0:
                break
            batch = self._find_snapshot_entities_chunk(
                snapshot_id,
                tenant_id=tenant_id,
                entity_kind=entity_kind,
                entity_kinds=entity_kinds,
                language=language,
                qualified_name=qualified_name,
                qualified_name_exact=qualified_name_exact,
                entity_fact_ids=id_chunk,
                repository_relative_path=repository_relative_path,
                path_prefix=path_prefix,
                limit=remaining,
            )
            for entity in batch:
                if entity.entity_fact_id in seen:
                    continue
                seen.add(entity.entity_fact_id)
                collected.append(entity)
        collected.sort(key=lambda entity: entity.entity_key)
        if limit is not None:
            collected = collected[:limit]
        return tuple(collected)

    def _find_snapshot_entities_chunk(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        entity_kind: str | None,
        entity_kinds: tuple[str, ...] | None,
        language: str | None,
        qualified_name: str | None,
        qualified_name_exact: bool,
        entity_fact_ids: tuple[str, ...] | None,
        repository_relative_path: str | None,
        path_prefix: str | None,
        limit: int | None,
    ) -> tuple[CodeEntityFact, ...]:
        clauses = ["m.snapshot_id = ?", "m.tenant_id = ?"]
        params: list[object] = [snapshot_id, tenant_id]
        if entity_kinds is not None:
            clauses.append(
                f"f.entity_kind IN ({_sql_in_placeholders(len(entity_kinds))})"
            )
            params.extend(entity_kinds)
        elif entity_kind is not None:
            clauses.append("f.entity_kind = ?")
            params.append(entity_kind)
        if language is not None:
            clauses.append("f.language = ?")
            params.append(language)
        if qualified_name is not None:
            if qualified_name_exact:
                clauses.append("f.qualified_name = ?")
                params.append(qualified_name)
            else:
                escaped = _escape_like(qualified_name)
                clauses.append("f.qualified_name LIKE ? ESCAPE '\\'")
                params.append(f"%{escaped}%")
        if entity_fact_ids is not None:
            clauses.append(
                f"f.entity_fact_id IN ({_sql_in_placeholders(len(entity_fact_ids))})"
            )
            params.extend(entity_fact_ids)
        if repository_relative_path is not None:
            clauses.append("f.repository_relative_path = ?")
            params.append(repository_relative_path)
        if path_prefix is not None and path_prefix != ".":
            escaped_descendants = _escape_like(path_prefix.rstrip("/") + "/") + "%"
            clauses.append(
                "(f.repository_relative_path = ? OR "
                "f.repository_relative_path LIKE ? ESCAPE '\\')"
            )
            params.append(path_prefix)
            params.append(escaped_descendants)
        sql = f"""
            SELECT f.* FROM gov_code_entity_facts f
            JOIN gov_code_graph_snapshot_entities m
              ON m.entity_fact_id = f.entity_fact_id
            WHERE {" AND ".join(clauses)}
            ORDER BY f.entity_key
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        self.entities_rows_fetched += len(rows)
        return tuple(self._entity_from_row(row) for row in rows)

    def get_snapshot_entity(
        self, snapshot_id: str, entity_fact_id: str, *, tenant_id: str
    ) -> CodeEntityFact | None:
        """Membership-checked single entity fetch for a snapshot."""

        row = self._conn.execute(
            """
            SELECT f.* FROM gov_code_entity_facts f
            JOIN gov_code_graph_snapshot_entities m
              ON m.entity_fact_id = f.entity_fact_id
            WHERE m.snapshot_id = ? AND m.tenant_id = ? AND f.entity_fact_id = ?
            """,
            (snapshot_id, tenant_id, entity_fact_id),
        ).fetchone()
        if row is None:
            return None
        self.entities_rows_fetched += 1
        return self._entity_from_row(row)

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
        self.relations_rows_fetched += len(rows)
        return tuple(self._relation_from_row(row) for row in rows)

    def find_snapshot_relations(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        relation_kinds: tuple[str, ...] | None = None,
        relation_fact_ids: tuple[str, ...] | None = None,
        source_entity_fact_ids: tuple[str, ...] | None = None,
        target_entity_fact_ids: tuple[str, ...] | None = None,
        either_entity_fact_ids: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> tuple[CodeRelationFact, ...]:
        """Bounded relation lookup using ``gov_code_relation_facts_expand`` columns."""

        if relation_kinds is not None and not relation_kinds:
            return ()
        if relation_fact_ids is not None and not relation_fact_ids:
            return ()
        if source_entity_fact_ids is not None and not source_entity_fact_ids:
            return ()
        if target_entity_fact_ids is not None and not target_entity_fact_ids:
            return ()
        if either_entity_fact_ids is not None and not either_entity_fact_ids:
            return ()

        # Chunk the largest caller-controlled IN lists beneath the backend limit.
        fact_id_chunks: list[tuple[str, ...] | None]
        if relation_fact_ids is None:
            fact_id_chunks = [None]
        else:
            fact_id_chunks = _chunked(relation_fact_ids, SQL_IN_CHUNK_SIZE)

        either_chunks: list[tuple[str, ...] | None]
        if either_entity_fact_ids is None:
            either_chunks = [None]
        else:
            either_chunks = _chunked(either_entity_fact_ids, SQL_IN_EITHER_CHUNK_SIZE)

        source_chunks: list[tuple[str, ...] | None]
        if source_entity_fact_ids is None:
            source_chunks = [None]
        else:
            source_chunks = _chunked(source_entity_fact_ids, SQL_IN_CHUNK_SIZE)

        target_chunks: list[tuple[str, ...] | None]
        if target_entity_fact_ids is None:
            target_chunks = [None]
        else:
            target_chunks = _chunked(target_entity_fact_ids, SQL_IN_CHUNK_SIZE)

        collected: list[CodeRelationFact] = []
        seen: set[str] = set()
        for fact_chunk in fact_id_chunks:
            for either_chunk in either_chunks:
                for source_chunk in source_chunks:
                    for target_chunk in target_chunks:
                        remaining = (
                            None if limit is None else max(limit - len(collected), 0)
                        )
                        if limit is not None and remaining == 0:
                            break
                        batch = self._find_snapshot_relations_chunk(
                            snapshot_id,
                            tenant_id=tenant_id,
                            relation_kinds=relation_kinds,
                            relation_fact_ids=fact_chunk,
                            source_entity_fact_ids=source_chunk,
                            target_entity_fact_ids=target_chunk,
                            either_entity_fact_ids=either_chunk,
                            limit=remaining,
                        )
                        for relation in batch:
                            if relation.relation_fact_id in seen:
                                continue
                            seen.add(relation.relation_fact_id)
                            collected.append(relation)
        collected.sort(key=lambda rel: (rel.relation_kind.value, rel.relation_fact_id))
        if limit is not None:
            collected = collected[:limit]
        return tuple(collected)

    def _find_snapshot_relations_chunk(
        self,
        snapshot_id: str,
        *,
        tenant_id: str,
        relation_kinds: tuple[str, ...] | None,
        relation_fact_ids: tuple[str, ...] | None,
        source_entity_fact_ids: tuple[str, ...] | None,
        target_entity_fact_ids: tuple[str, ...] | None,
        either_entity_fact_ids: tuple[str, ...] | None,
        limit: int | None,
    ) -> tuple[CodeRelationFact, ...]:
        clauses = ["m.snapshot_id = ?", "m.tenant_id = ?"]
        params: list[object] = [snapshot_id, tenant_id]
        if relation_kinds is not None:
            clauses.append(
                f"f.relation_kind IN ({_sql_in_placeholders(len(relation_kinds))})"
            )
            params.extend(relation_kinds)
        if relation_fact_ids is not None:
            clauses.append(
                f"f.relation_fact_id IN ({_sql_in_placeholders(len(relation_fact_ids))})"
            )
            params.extend(relation_fact_ids)
        if source_entity_fact_ids is not None:
            clauses.append(
                "f.source_entity_fact_id IN "
                f"({_sql_in_placeholders(len(source_entity_fact_ids))})"
            )
            params.extend(source_entity_fact_ids)
        if target_entity_fact_ids is not None:
            clauses.append(
                "f.target_entity_fact_id IN "
                f"({_sql_in_placeholders(len(target_entity_fact_ids))})"
            )
            params.extend(target_entity_fact_ids)
        if either_entity_fact_ids is not None:
            placeholders = _sql_in_placeholders(len(either_entity_fact_ids))
            clauses.append(
                f"(f.source_entity_fact_id IN ({placeholders}) "
                f"OR f.target_entity_fact_id IN ({placeholders}))"
            )
            params.extend(either_entity_fact_ids)
            params.extend(either_entity_fact_ids)
        sql = f"""
            SELECT f.* FROM gov_code_relation_facts f
            JOIN gov_code_graph_snapshot_relations m
              ON m.relation_fact_id = f.relation_fact_id
            WHERE {" AND ".join(clauses)}
            ORDER BY f.relation_kind, f.relation_fact_id
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        self.relations_rows_fetched += len(rows)
        return tuple(self._relation_from_row(row) for row in rows)

    def get_entity_fact(self, entity_fact_id: str) -> CodeEntityFact | None:
        row = self._conn.execute(
            "SELECT * FROM gov_code_entity_facts WHERE entity_fact_id = ?",
            (entity_fact_id,),
        ).fetchone()
        if row is None:
            return None
        self.entities_rows_fetched += 1
        return self._entity_from_row(row)

    def get_relation_fact(self, relation_fact_id: str) -> CodeRelationFact | None:
        row = self._conn.execute(
            "SELECT * FROM gov_code_relation_facts WHERE relation_fact_id = ?",
            (relation_fact_id,),
        ).fetchone()
        if row is None:
            return None
        self.relations_rows_fetched += 1
        return self._relation_from_row(row)

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
