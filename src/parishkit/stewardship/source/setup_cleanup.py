"""Scheduler and worker ownership for expired setup source disposal."""

from uuid import uuid4

from django.db import connection
from django.db.models import Exists, OuterRef

from parishkit.stewardship.accounts.runtime_models import SystemConfiguration
from parishkit.stewardship.accounts.setup_models import SetupAttempt
from parishkit.stewardship.campaigns.work_locks import (
    require_work_order,
    work_transaction,
)
from parishkit.stewardship.jobs.dispatch import Handler, RecoveryPlan
from parishkit.stewardship.jobs.models import TaskRun
from parishkit.stewardship.jobs.ownership import database_now, lock_task_claim
from parishkit.stewardship.jobs.phases import TaskPhase
from parishkit.stewardship.jobs.queues import WorkQueue
from parishkit.stewardship.jobs.scheduler import SchedulerGuard
from parishkit.stewardship.jobs.storage import TaskStatus, _status, change_run, enqueue
from parishkit.stewardship.storage import StorageInvariantError

from .leases import acquire_source, release_source
from .setup_admission import admit_setup_task, source_available
from .setup_disposal import TASK_TYPE, dispose_batch, owned_snapshots
from .version_models import ENTITY_MODELS


def _attempt(status, *, creating=False):
    """Opaque queue IDs must match a real expired setup and exact Task status."""
    require_work_order()
    if not isinstance(status, TaskStatus) or status.task_type != TASK_TYPE:
        raise PermissionError("This Task cannot dispose setup source data.")
    if (
        not creating
        and not TaskRun.objects.filter(
            pk=status.run_id,
            root_id=status.root_id,
            task_type=TASK_TYPE,
            domain_request_id=status.domain_request_id,
            state=status.state,
            version=status.version,
            fence=status.fence,
            worker_id=status.worker_id,
        ).exists()
    ):
        raise PermissionError("Setup cleanup Task ownership differs.")
    return SetupAttempt.objects.get(pk=status.domain_request_id, state="expired")


def pending(attempt_id):
    """Read concrete source membership only in the actual worker, never scheduler."""
    snapshots = owned_snapshots(attempt_id)
    return snapshots.exclude(state="rejected").exists() or any(
        membership.objects.filter(snapshot_id__in=snapshots.values("id")).exists()
        for _, membership in ENTITY_MODELS.values()
    )


def recover_cleanup(status):
    """A drained cleanup is idempotent; a retry rechecks every remaining row."""
    _attempt(status)
    if (
        status.state != "abandoned"
        or not source_available()
        or not SystemConfiguration.objects.filter(
            restore_review_required=False
        ).exists()
    ):
        return None
    return RecoveryPlan("recovery_retry", retry_seconds=30)


def admit_cleanup(action, status):
    """Closed transitions never translate an empty snapshot count into success."""
    attempt = _attempt(status, creating=action == "enqueue")
    if action == "lease_expired" or (
        action == "recovery_hint" and status.state == "running"
    ):
        return True
    if action in {"recovery_hint", "recovery_retry"}:
        return recover_cleanup(status) is not None
    if not SystemConfiguration.objects.filter(restore_review_required=False).exists():
        return False
    if action == "complete":
        return not pending(attempt.pk)
    if action in {"claim", "hint"}:
        return source_available()
    return action in {"enqueue", "effect", "heartbeat", "progress"}


def produce_setup_cleanup(guard):
    """Queue at most one original expired attempt per scheduler pass, idempotently."""
    if not isinstance(guard, SchedulerGuard):
        raise TypeError("Setup cleanup requires its actual scheduler guard.")
    if connection.in_atomic_block:
        raise StorageInvariantError("Setup cleanup production owns its transaction.")
    guard.check()
    with work_transaction():
        if not SystemConfiguration.objects.filter(
            restore_review_required=False
        ).exists():
            return ()
        scheduled = TaskRun.objects.filter(
            task_type=TASK_TYPE, domain_request_id=OuterRef("id")
        )
        attempt = (
            SetupAttempt.objects.filter(
                state="expired",
                source_task_id__isnull=False,
            )
            .filter(~Exists(scheduled))
            .order_by("created_at", "id")
            .first()
        )
        if attempt is None:
            return ()
        result = enqueue(
            task_type=TASK_TYPE,
            domain_request_id=attempt.pk,
            actor_id=None,
            correlation_id=uuid4(),
            idempotency_key=attempt.pk,
            admit=admit_cleanup,
        )
    guard.check()
    return (result.run_id,)


def cleanup_handler(*, scheduler=False):
    """Only the worker registry binds deletion; scheduling contains metadata only."""

    def unavailable(execution):
        """A scheduler has neither source payload access nor executable deletion."""
        raise PermissionError("The scheduler cannot dispose source data.")

    return Handler(
        WorkQueue.GENERAL,
        admit_cleanup,
        unavailable if scheduler else _execute,
        recover=recover_cleanup,
        scope=work_transaction,
    )


def _settle_original(attempt_id, execution):
    """Cancel waiting original reads; live workers retain their normal expiry path."""
    attempt = SetupAttempt.objects.get(pk=attempt_id, state="expired")
    for row in TaskRun.objects.filter(
        root_id=attempt.source_task_id,
        task_type="setup_source_load",
        domain_request_id=attempt.pk,
    ).order_by("created_at", "id"):
        if row.state == "running" and row.lease_expires_at <= database_now():
            change_run(
                run_id=row.pk,
                expected_version=row.version,
                action="lease_expired",
                actor_id=None,
                correlation_id=execution.correlation_id,
                admit=admit_setup_task,
            )
            row.refresh_from_db()
        if row.state in {"queued", "retry_wait", "abandoned"}:
            change_run(
                run_id=row.pk,
                expected_version=row.version,
                action="recovery_cancel" if row.state == "abandoned" else "safe_cancel",
                actor_id=execution.claim.worker_id,
                correlation_id=execution.correlation_id,
                admit=admit_setup_task,
            )


def _execute(execution):
    """Retire drained manifests and delete short batches under both renewed fences."""
    if connection.in_atomic_block or not execution.control.active:
        raise StorageInvariantError("Source disposal requires maintained execution.")
    with execution.effect():
        claim = acquire_source(
            task_id=execution.claim.run_id,
            task_fence=execution.claim.fence,
            worker_id=execution.claim.worker_id,
            phase="full",
        )
    done = 0
    with execution.maintain_source(claim):
        while True:
            with execution.effect():
                count = dispose_batch(execution, claim)
            if count is None:
                break
            done += count
            execution.progress(done, done, phase=TaskPhase.DELETING)
    with execution.control.lock:
        with work_transaction():
            status = _status(lock_task_claim(execution.claim))
            release_source(claim)
            _settle_original(status.domain_request_id, execution)
            change_run(
                run_id=status.run_id,
                expected_version=status.version,
                action="complete",
                actor_id=execution.claim.worker_id,
                correlation_id=execution.correlation_id,
                fence=execution.claim.fence,
                admit=admit_cleanup,
            )
        execution.control.finished.set()
