"""Admin cancellation is durable intent, not impersonation of a live worker."""

from uuid import uuid4

import pytest

from parishkit.stewardship.campaigns import cleanup_tasks
from parishkit.stewardship.campaigns.cleanup_requests import request_cancellation
from parishkit.stewardship.campaigns.cleanup_tasks import TASK_TYPE, cleanup_handler
from parishkit.stewardship.campaigns.credential_models import CampaignCredentialState
from parishkit.stewardship.campaigns.production_models import (
    ProductionCleanupTarget,
    ProductionTransitionRequest,
)
from parishkit.stewardship.deployment import ServiceRole
from parishkit.stewardship.jobs.dispatch import Execution, claim_hint, recover_hint
from parishkit.stewardship.jobs.lifetime import maintain_execution
from parishkit.stewardship.jobs.models import TaskRun
from parishkit.stewardship.jobs.queues import WorkQueue
from parishkit.stewardship.jobs.storage import _status as task_status

from .test_background_grants_postgresql import task_login
from .test_cleanup_tasks_postgresql import queued, run
from .test_taskrun_postgresql import act as task_act
from .test_taskrun_postgresql import expire

pytestmark = pytest.mark.django_db(transaction=True)


def cancel(request_id):
    """Synthetic Admin owns intent; the actual worker still owns stopping itself."""
    request = ProductionTransitionRequest.objects.get(pk=request_id)
    return request_cancellation(
        request_id=request.pk,
        command_id=uuid4(),
        expected_version=request.version,
        actor_id=uuid4(),
        correlation_id=uuid4(),
        admit=lambda *args: True,
    )


def assert_cancelled(status):
    """Cancelling releases only this gate and retains the recorded cleanup result."""
    request = ProductionTransitionRequest.objects.get(pk=status.request_id)
    assert request.state == "cancelled"
    assert not CampaignCredentialState.objects.get(
        campaign_id=request.campaign_id
    ).go_live_gate
    assert TaskRun.objects.get(pk=status.task_id).state == "cancelled"
    return request


def test_queued_cancellation_is_immediate_and_does_not_delete(response_service):
    """There is no worker fence to impersonate before the task is claimed."""
    status = queued(response_service)
    cancel(status.request_id)
    request = assert_cancelled(status)
    assert request.processed_count == 0
    assert (
        ProductionCleanupTarget.objects.filter(request=request).count()
        == request.inventory_total
    )


@pytest.mark.parametrize("crashed", [False, True])
def test_running_cancellation_is_observed_by_worker_or_recovery(
    response_service, crashed
):
    """An Admin cannot cancel an in-flight claim directly; a boundary finishes it."""
    status = queued(response_service)
    handlers = {TASK_TYPE: cleanup_handler()}
    with task_login(ServiceRole.WORKER, exact=True):
        execution = claim_hint(
            status.task_id,
            queue=WorkQueue.GENERAL,
            worker_id=uuid4(),
            handlers=handlers,
        )
    assert cancel(status.request_id).state == "cleanup_queued"
    assert TaskRun.objects.get(pk=status.task_id).state == "running"
    if crashed:
        task = task_status(TaskRun.objects.get(pk=status.task_id))
        expire(task_act(task, "heartbeat", lease_seconds=1))
        with task_login(ServiceRole.WORKER, exact=True):
            assert recover_hint(
                status.task_id,
                queue=WorkQueue.GENERAL,
                worker_id=uuid4(),
                handlers=handlers,
            )
    else:
        with (
            task_login(ServiceRole.WORKER, exact=True, reconnect=True),
            maintain_execution(execution),
        ):
            execution.handler.execute(execution)
    assert assert_cancelled(status).processed_count == 0


def test_cancel_between_batches_then_new_cleanup_finishes_remaining_data(
    response_service, monkeypatch
):
    """The next cleanup also removes abandoned private inventory membership."""
    status = queued(response_service)
    original_batch = cleanup_tasks.apply_checkpoint
    original_progress = Execution.progress

    def small_batch(request_id, claim):
        """Ensure this test has more than one independently committed batch."""
        return original_batch(request_id, claim, maximum=2)

    def stop_after_progress(execution, current, total, **options):
        """Simulate an Admin's separate request after the batch has committed."""
        result = original_progress(execution, current, total, **options)
        cancel(status.request_id)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(cleanup_tasks, "apply_checkpoint", small_batch)
        patch.setattr(Execution, "progress", stop_after_progress)
        assert run(status)
    request = assert_cancelled(status)
    assert 0 < request.processed_count < request.inventory_total
    retained_progress = request.processed_count
    assert ProductionCleanupTarget.objects.filter(request=request).exists()
    subsequent = queued(response_service)
    assert run(subsequent)
    assert not ProductionCleanupTarget.objects.exists()
    request.refresh_from_db()
    assert request.processed_count == retained_progress and request.state == "cancelled"
