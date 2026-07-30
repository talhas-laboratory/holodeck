"""Governed command handling: resolve facts from durable records (enforced kernel)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from holodeck_governance.domain.catalogs.errors import DomainErrorCode
from holodeck_governance.domain.catalogs.reasons import ReasonCode
from holodeck_governance.domain.commands.envelope import CommandEnvelope, semantic_fingerprint
from holodeck_governance.domain.commands.receipt import CommandReceipt
from holodeck_governance.domain.errors import (
    CrossTenantAccessError,
    IdempotencyConflictError,
    MissingAuthorityError,
    NotFoundGovernanceError,
    StaleRevisionError,
)
from holodeck_governance.domain.evaluation.snapshot import EvaluationResult, EvaluationSnapshot
from holodeck_governance.domain.evaluators.run_transition import evaluate_run_transition
from holodeck_governance.domain.evaluators.task_transition import evaluate_task_transition
from holodeck_governance.domain.ids import generate_uuidv7
from holodeck_governance.domain.records.decision import DecisionRecord
from holodeck_governance.storage.sqlite.authority import SqliteAuthorityRepository
from holodeck_governance.storage.sqlite.migrations import migrate_governance
from holodeck_governance.storage.sqlite.policy import SqlitePolicyRepository
from holodeck_governance.storage.sqlite.records import SqliteRecordRepository
from holodeck_governance.storage.sqlite.repos import (
    SqliteCommandReceiptRepository,
    SqliteDomainEventRepository,
    SqliteEvaluationRepository,
    SqliteOutboxRepository,
    SqliteTransitionRecordRepository,
)
from holodeck_governance.storage.sqlite.runs import SqliteRunRepository
from holodeck_governance.storage.sqlite.tasks import SqliteTaskRepository
from holodeck_governance.storage.sqlite.uow import SqliteUnitOfWork

TASK_TRANSITION_EVALUATOR_ID = "m1.TaskTransitionEvaluator.v1"
RUN_TRANSITION_EVALUATOR_ID = "m1.RunTransitionEvaluator.v1"


def ensure_command_tables(conn: sqlite3.Connection) -> None:
    """Compatibility shim: schema is owned by numbered migrations."""

    migrate_governance(conn)


class CommandService:
    """Commands are the sole governed mutation path; facts come from storage."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        fault_before: str | None = None,
    ) -> None:
        self._conn = conn
        self._fault_before = fault_before
        ensure_command_tables(conn)
        self._receipts = SqliteCommandReceiptRepository(conn)
        self._events = SqliteDomainEventRepository(conn)
        self._outbox = SqliteOutboxRepository(conn)
        self._transitions = SqliteTransitionRecordRepository(conn)
        self._evaluations = SqliteEvaluationRepository(conn)
        self._tasks = SqliteTaskRepository(conn)
        self._runs = SqliteRunRepository(conn)
        self._authority = SqliteAuthorityRepository(conn)
        self._policy = SqlitePolicyRepository(conn)
        self._records = SqliteRecordRepository(conn)

    def handle(
        self,
        command: CommandEnvelope,
        *,
        now: datetime | None = None,
    ) -> CommandReceipt:
        stamp = now or command.issued_at
        fingerprint = semantic_fingerprint(command)

        existing = self._receipts.get_by_idempotency(
            command.tenant_id, command.idempotency_key
        )
        if existing is not None:
            stored_hash, receipt = existing
            if stored_hash != fingerprint:
                raise IdempotencyConflictError(
                    "idempotency key reused with different payload"
                )
            return receipt

        if command.command_type == "task.transition":
            return self._handle_task_transition(
                command, fingerprint=fingerprint, stamp=stamp
            )
        if command.command_type == "run.transition":
            return self._handle_run_transition(
                command, fingerprint=fingerprint, stamp=stamp
            )
        return self._reject(
            command,
            fingerprint=fingerprint,
            stamp=stamp,
            reason_codes=(ReasonCode.DENY_MALFORMED_COMMAND.value,),
            error_code=DomainErrorCode.MALFORMED_COMMAND.value,
            emit_event=True,
        )

    def _handle_task_transition(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
    ) -> CommandReceipt:
        try:
            actor = self._authority.require_actor(command.actor_id)
            if actor.tenant_id != command.tenant_id:
                return self._reject(
                    command,
                    fingerprint=fingerprint,
                    stamp=stamp,
                    reason_codes=(ReasonCode.DENY_TENANT_ISOLATION.value,),
                    error_code=DomainErrorCode.CROSS_TENANT_ACCESS.value,
                    emit_event=False,
                )
            task = self._tasks.require_tenant_task(
                object_id=command.target_object_id,
                tenant_id=command.tenant_id,
            )
            permitted, grant_deny = self._authority.actor_may_transition(
                tenant_id=command.tenant_id,
                actor_id=command.actor_id,
                subject_object_id=task.object_id,
                subject_revision=task.revision,
                workspace_object_id=task.workspace_object_id,
                at=stamp,
            )
            policy, binding_ids = self._policy.active_policy(
                tenant_id=command.tenant_id,
                evaluator_id=TASK_TRANSITION_EVALUATOR_ID,
                at=stamp,
            )
            approval_rev = None
            required_approvals = int(policy.get("required_approvals", "0") or "0")
            authorized_approvers: tuple[str, ...] = ()
            if required_approvals >= 1:
                ok, approval_rev, authorized_approvers = self._authority.approvals_satisfy(
                    tenant_id=command.tenant_id,
                    subject_object_id=task.object_id,
                    subject_revision=task.revision,
                    required=required_approvals,
                    workspace_object_id=task.workspace_object_id,
                    at=stamp,
                )
                if not ok:
                    return self._reject(
                        command,
                        fingerprint=fingerprint,
                        stamp=stamp,
                        reason_codes=(ReasonCode.DENY_STALE_APPROVAL.value,),
                        error_code=DomainErrorCode.STALE_REVISION.value,
                        emit_event=True,
                    )
            target = str(command.payload["to_state"])
            policy_binding_id = binding_ids[-1] if binding_ids else None
            selected_authority = {
                "actor_id": command.actor_id,
                "permission": "transition_task",
                "required_approvals": str(required_approvals),
                "authorized_approver_count": str(len(authorized_approvers)),
            }
            if authorized_approvers:
                selected_authority["authorized_approvers"] = ",".join(authorized_approvers)
            snapshot, evaluation, definition = evaluate_task_transition(
                tenant_id=command.tenant_id,
                subject_object_id=command.target_object_id,
                subject_revision=task.revision,
                expected_revision=command.expected_revision,
                current_state=task.state,
                target_state=target,
                actor_permitted=permitted,
                created_at=stamp,
                approval_subject_revision=approval_rev,
                grant_ok=None if permitted else False,
                grant_deny_reason=grant_deny,
                policy_binding_id=policy_binding_id,
                selected_authority=selected_authority,
            )
            if evaluation.outcome != "allow" or definition is None:
                return self._deny_evaluation(
                    command,
                    fingerprint=fingerprint,
                    stamp=stamp,
                    evaluation=(snapshot, evaluation),
                )
            return self._accept_subject_transition(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                subject_kind="Task",
                current=task,
                target_state=target,
                definition_version=definition,
                evaluation=(snapshot, evaluation),
            )
        except (
            CrossTenantAccessError,
            NotFoundGovernanceError,
            StaleRevisionError,
            MissingAuthorityError,
            KeyError,
        ) as exc:
            return self._map_exception_reject(
                command, fingerprint=fingerprint, stamp=stamp, exc=exc
            )

    def _handle_run_transition(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
    ) -> CommandReceipt:
        try:
            actor = self._authority.require_actor(command.actor_id)
            if actor.tenant_id != command.tenant_id:
                return self._reject(
                    command,
                    fingerprint=fingerprint,
                    stamp=stamp,
                    reason_codes=(ReasonCode.DENY_TENANT_ISOLATION.value,),
                    error_code=DomainErrorCode.CROSS_TENANT_ACCESS.value,
                    emit_event=False,
                )
            run = self._runs.require_tenant_run(
                object_id=command.target_object_id,
                tenant_id=command.tenant_id,
            )
            # Authority is scoped via the parent task workspace when present.
            task = self._tasks.get_head_task(run.task_object_id)
            workspace_object_id = task.workspace_object_id if task else None
            permitted, grant_deny = self._authority.actor_may_transition(
                tenant_id=command.tenant_id,
                actor_id=command.actor_id,
                subject_object_id=run.object_id,
                subject_revision=run.revision,
                workspace_object_id=workspace_object_id,
                at=stamp,
                permission="transition_run",
            )
            target = str(command.payload["to_state"])
            snapshot, evaluation, definition = evaluate_run_transition(
                tenant_id=command.tenant_id,
                subject_object_id=command.target_object_id,
                subject_revision=run.revision,
                expected_revision=command.expected_revision,
                current_state=run.state,
                target_state=target,
                actor_permitted=permitted,
                created_at=stamp,
                grant_ok=None if permitted else False,
                grant_deny_reason=grant_deny,
            )
            if evaluation.outcome != "allow" or definition is None:
                return self._deny_evaluation(
                    command,
                    fingerprint=fingerprint,
                    stamp=stamp,
                    evaluation=(snapshot, evaluation),
                )
            return self._accept_subject_transition(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                subject_kind="Run",
                current=run,
                target_state=target,
                definition_version=definition,
                evaluation=(snapshot, evaluation),
            )
        except (
            CrossTenantAccessError,
            NotFoundGovernanceError,
            StaleRevisionError,
            MissingAuthorityError,
            KeyError,
        ) as exc:
            return self._map_exception_reject(
                command, fingerprint=fingerprint, stamp=stamp, exc=exc
            )

    def _deny_evaluation(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
        evaluation: tuple[EvaluationSnapshot, EvaluationResult],
    ) -> CommandReceipt:
        error = DomainErrorCode.INVALID_TRANSITION.value
        reasons = evaluation[1].reason_codes
        if ReasonCode.DENY_MISSING_AUTHORITY.value in reasons:
            error = DomainErrorCode.MISSING_AUTHORITY.value
        if ReasonCode.DENY_STALE_REVISION.value in reasons:
            error = DomainErrorCode.STALE_REVISION.value
        if ReasonCode.DENY_STALE_APPROVAL.value in reasons:
            error = DomainErrorCode.STALE_REVISION.value
        if ReasonCode.DENY_GRANT_EXPIRED.value in reasons:
            error = DomainErrorCode.GRANT_EXPIRED.value
        if ReasonCode.DENY_GRANT_REVOKED.value in reasons:
            error = DomainErrorCode.GRANT_REVOKED.value
        if ReasonCode.DENY_GRANT_WRONG_REVISION.value in reasons:
            error = DomainErrorCode.GRANT_WRONG_REVISION.value
        return self._reject(
            command,
            fingerprint=fingerprint,
            stamp=stamp,
            reason_codes=reasons,
            error_code=error,
            evaluation=evaluation,
            emit_event=True,
        )

    def _map_exception_reject(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
        exc: Exception,
    ) -> CommandReceipt:
        if isinstance(exc, CrossTenantAccessError):
            return self._reject(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                reason_codes=(ReasonCode.DENY_TENANT_ISOLATION.value,),
                error_code=DomainErrorCode.CROSS_TENANT_ACCESS.value,
                emit_event=False,
            )
        if isinstance(exc, NotFoundGovernanceError):
            return self._reject(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                reason_codes=(ReasonCode.DENY_MALFORMED_COMMAND.value,),
                error_code=exc.code.value,
                emit_event=True,
            )
        if isinstance(exc, StaleRevisionError):
            return self._reject(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                reason_codes=(ReasonCode.DENY_STALE_REVISION.value,),
                error_code=DomainErrorCode.STALE_REVISION.value,
                emit_event=True,
            )
        if isinstance(exc, MissingAuthorityError):
            return self._reject(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                reason_codes=(ReasonCode.DENY_MISSING_AUTHORITY.value,),
                error_code=DomainErrorCode.MISSING_AUTHORITY.value,
                emit_event=True,
            )
        return self._reject(
            command,
            fingerprint=fingerprint,
            stamp=stamp,
            reason_codes=(ReasonCode.DENY_MALFORMED_COMMAND.value,),
            error_code=DomainErrorCode.MALFORMED_COMMAND.value,
            emit_event=True,
        )

    def _accept_subject_transition(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
        subject_kind: str,
        current,
        target_state: str,
        definition_version: str,
        evaluation: tuple[EvaluationSnapshot, EvaluationResult],
    ) -> CommandReceipt:
        receipt = CommandReceipt(
            receipt_id=generate_uuidv7(),
            command_id=command.command_id,
            tenant_id=command.tenant_id,
            outcome="accepted",
            reason_codes=evaluation[1].reason_codes,
            error_code=None,
            created_at=stamp,
            evaluation_result_id=evaluation[1].result_id,
        )
        event_id = generate_uuidv7()
        decision_object_id = generate_uuidv7()
        uow = SqliteUnitOfWork(self._conn, fault_before=self._fault_before)

        def write_receipt(conn: sqlite3.Connection) -> None:
            try:
                SqliteCommandReceiptRepository(conn).save(
                    receipt,
                    idempotency_key=command.idempotency_key,
                    semantic_hash=fingerprint,
                )
            except sqlite3.IntegrityError as exc:
                raise IdempotencyConflictError(
                    "idempotency key collision under concurrent write"
                ) from exc

        def write_evaluation(conn: sqlite3.Connection) -> None:
            SqliteEvaluationRepository(conn).save_snapshot_and_result(
                evaluation[0], evaluation[1]
            )

        def write_head(conn: sqlite3.Connection) -> None:
            if subject_kind == "Task":
                SqliteTaskRepository(conn).apply_transition(
                    current=current,
                    to_state=target_state,
                    actor_id=command.actor_id,
                    created_at=stamp,
                    expected_revision=command.expected_revision,
                )
            else:
                SqliteRunRepository(conn).apply_transition(
                    current=current,
                    to_state=target_state,
                    actor_id=command.actor_id,
                    created_at=stamp,
                    expected_revision=command.expected_revision,
                )

        def write_transition(conn: sqlite3.Connection) -> None:
            SqliteTransitionRecordRepository(conn).append(
                tenant_id=command.tenant_id,
                subject_object_id=command.target_object_id,
                from_state=current.state,
                to_state=target_state,
                definition_version=definition_version,
                created_at=stamp.isoformat(),
                command_id=command.command_id,
            )

        def write_decision(conn: sqlite3.Connection) -> None:
            SqliteRecordRepository(conn).save_decision(
                DecisionRecord(
                    record_id=generate_uuidv7(),
                    tenant_id=command.tenant_id,
                    object_id=decision_object_id,
                    revision=1,
                    subject_object_id=command.target_object_id,
                    subject_revision=current.revision,
                    outcome="accepted",
                    created_at=stamp,
                    created_by_actor_id=command.actor_id,
                ),
                command_id=command.command_id,
            )

        def write_event(conn: sqlite3.Connection) -> None:
            SqliteDomainEventRepository(conn).append(
                event_id=event_id,
                tenant_id=command.tenant_id,
                event_type="governance.command.accepted",
                correlation_id=command.correlation_id,
                causation_id=command.command_id,
                actor_id=command.actor_id,
                payload_schema_version="m1.event.command_accepted.v1",
                occurred_at=stamp.isoformat(),
                subject_object_id=command.target_object_id,
                subject_revision=current.revision,
                payload={
                    "command_id": command.command_id,
                    "receipt_id": receipt.receipt_id,
                    "evaluation_result_id": receipt.evaluation_result_id,
                    "subject_object_id": command.target_object_id,
                    "subject_kind": subject_kind,
                    "decision_object_id": decision_object_id,
                    "from_state": current.state,
                    "to_state": target_state,
                },
                created_at=stamp.isoformat(),
            )

        def write_outbox(conn: sqlite3.Connection) -> None:
            SqliteOutboxRepository(conn).enqueue(
                tenant_id=command.tenant_id,
                domain_event_id=event_id,
                delivery_purpose="command_accepted",
                dedup_key=f"{command.tenant_id}:{event_id}:command_accepted",
                created_at=stamp.isoformat(),
            )

        def write_links(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO gov_command_subject_links(
                    command_id, tenant_id, subject_object_id, subject_revision,
                    link_kind, linked_id
                ) VALUES (?, ?, ?, ?, 'evaluation', ?)
                """,
                (
                    command.command_id,
                    command.tenant_id,
                    command.target_object_id,
                    current.revision,
                    evaluation[1].result_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO gov_command_subject_links(
                    command_id, tenant_id, subject_object_id, subject_revision,
                    link_kind, linked_id
                ) VALUES (?, ?, ?, ?, 'decision', ?)
                """,
                (
                    command.command_id,
                    command.tenant_id,
                    command.target_object_id,
                    current.revision,
                    decision_object_id,
                ),
            )

        uow.add("receipt", write_receipt)
        uow.add("evaluation", write_evaluation)
        uow.add("head", write_head)
        uow.add("transition", write_transition)
        uow.add("decision", write_decision)
        uow.add("event", write_event)
        uow.add("outbox", write_outbox)
        uow.add("links", write_links)
        try:
            uow.commit()
        except IdempotencyConflictError:
            loaded = self._receipts.get_by_idempotency(
                command.tenant_id, command.idempotency_key
            )
            if loaded is None:
                raise
            stored_hash, prior = loaded
            if stored_hash != fingerprint:
                raise
            return prior
        except StaleRevisionError:
            # Competing transition lost the head race: structured reject with eval.
            return self._reject(
                command,
                fingerprint=fingerprint,
                stamp=stamp,
                reason_codes=(ReasonCode.DENY_STALE_REVISION.value,),
                error_code=DomainErrorCode.STALE_REVISION.value,
                evaluation=evaluation,
                emit_event=True,
            )
        return receipt

    def _reject(
        self,
        command: CommandEnvelope,
        *,
        fingerprint: str,
        stamp: datetime,
        reason_codes: tuple[str, ...],
        error_code: str,
        evaluation: tuple[EvaluationSnapshot, EvaluationResult] | None = None,
        emit_event: bool = True,
    ) -> CommandReceipt:
        receipt = CommandReceipt(
            receipt_id=generate_uuidv7(),
            command_id=command.command_id,
            tenant_id=command.tenant_id,
            outcome="rejected",
            reason_codes=reason_codes,
            error_code=error_code,
            created_at=stamp,
            evaluation_result_id=evaluation[1].result_id if evaluation else None,
        )
        uow = SqliteUnitOfWork(self._conn, fault_before=self._fault_before)

        def write_receipt(conn: sqlite3.Connection) -> None:
            try:
                SqliteCommandReceiptRepository(conn).save(
                    receipt,
                    idempotency_key=command.idempotency_key,
                    semantic_hash=fingerprint,
                )
            except sqlite3.IntegrityError as exc:
                raise IdempotencyConflictError(
                    "idempotency key collision under concurrent write"
                ) from exc

        def write_evaluation(conn: sqlite3.Connection) -> None:
            if evaluation is not None:
                SqliteEvaluationRepository(conn).save_snapshot_and_result(
                    evaluation[0], evaluation[1]
                )

        def write_event(conn: sqlite3.Connection) -> None:
            subject_object_id = None
            owned = conn.execute(
                """
                SELECT 1 FROM gov_objects
                WHERE object_id = ? AND tenant_id = ?
                """,
                (command.target_object_id, command.tenant_id),
            ).fetchone()
            if owned is not None:
                subject_object_id = command.target_object_id
            SqliteDomainEventRepository(conn).append(
                tenant_id=command.tenant_id,
                event_type="governance.command.rejected",
                correlation_id=command.correlation_id,
                causation_id=command.command_id,
                actor_id=command.actor_id,
                payload_schema_version="m1.event.command_rejected.v1",
                occurred_at=stamp.isoformat(),
                subject_object_id=subject_object_id,
                subject_revision=command.expected_revision,
                payload={
                    "command_id": command.command_id,
                    "receipt_id": receipt.receipt_id,
                    "error_code": error_code,
                    "reason_codes": list(reason_codes),
                },
                created_at=stamp.isoformat(),
            )

        uow.add("receipt", write_receipt)
        if evaluation is not None:
            uow.add("evaluation", write_evaluation)
        if emit_event:
            uow.add("event", write_event)
        try:
            uow.commit()
        except IdempotencyConflictError:
            loaded = self._receipts.get_by_idempotency(
                command.tenant_id, command.idempotency_key
            )
            if loaded is None:
                raise
            stored_hash, prior = loaded
            if stored_hash != fingerprint:
                raise
            return prior
        return receipt
