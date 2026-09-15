"""Atomic capture and replay keep readiness ownership outside the cleanup worker."""

from uuid import uuid4

import pytest

from parishkit.stewardship.campaigns import cleanup_requests
from parishkit.stewardship.campaigns.credential_models import CampaignCredentialState
from parishkit.stewardship.campaigns.production_models import (
    ProductionTransitionRequest,
)

from .test_cleanup_tasks_postgresql import queued, run

pytestmark = pytest.mark.django_db(transaction=True)


def original_intent(request):
    """Reconstruct the synthetic Admin's original acknowledged request."""
    return dict(
        campaign_id=request.campaign_id,
        request_key=request.request_key,
        actor_id=request.initiated_by_id,
        correlation_id=uuid4(),
        readiness_digest=request.aggregate.readiness_digest,
        acknowledged_at=request.acknowledged_at,
        reauthenticated_at=request.reauthenticated_at,
        admit=lambda *args: True,
    )


def test_begin_replay_after_deletion_uses_original_evidence(response_service):
    """Changed current row counts cannot invalidate the original idempotency key."""
    status = queued(response_service)
    intent = original_intent(
        ProductionTransitionRequest.objects.get(pk=status.request_id)
    )
    assert run(status)
    replay = cleanup_requests.begin_cleanup(**intent)
    assert replay.request_id == status.request_id and replay.state == "cleanup_complete"
    assert replay.inventory_total == status.inventory_total
    assert ProductionTransitionRequest.objects.count() == 1
    with pytest.raises(PermissionError):
        cleanup_requests.begin_cleanup(**(intent | {"admit": lambda *args: False}))
    with pytest.raises(ValueError, match="already bound"):
        cleanup_requests.begin_cleanup(**(intent | {"readiness_digest": "a" * 64}))


def test_failed_sealing_rolls_back_gate_epoch_and_task(response_service, monkeypatch):
    """The request is never published to a worker without its entire manifest."""
    before = CampaignCredentialState.objects.get(campaign=response_service.campaign)

    def fail(*args):
        """Fail at the last step of the composed capture transaction."""
        raise RuntimeError("synthetic seal interruption")

    monkeypatch.setattr(cleanup_requests, "seal_manifest", fail)
    with pytest.raises(RuntimeError, match="synthetic seal interruption"):
        queued(response_service)
    after = CampaignCredentialState.objects.get(pk=before.pk)
    assert (after.version, after.go_live_gate, after.rehearsal_epoch_id) == (
        before.version,
        before.go_live_gate,
        before.rehearsal_epoch_id,
    )
    assert not ProductionTransitionRequest.objects.exists()
    from parishkit.stewardship.jobs.models import TaskRun

    assert not TaskRun.objects.filter(task_type="production_cleanup").exists()
