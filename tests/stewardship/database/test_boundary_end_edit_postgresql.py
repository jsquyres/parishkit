"""End-date preflight cannot overlook a close worker claimed before binding."""

from uuid import uuid4

import pytest

from parishkit.stewardship.accounts.configuration_installation import install_request
from parishkit.stewardship.campaigns.admission import (
    CampaignAdmissionUnavailable,
    close_work_running,
)
from parishkit.stewardship.campaigns.lifecycle import Action
from parishkit.stewardship.campaigns.models import CampaignBoundaryOccurrence
from parishkit.stewardship.campaigns.work_locks import work_transaction
from parishkit.stewardship.jobs.storage import enqueue

from .campaign_builders import (
    admit_test_work,
    campaign_clock,
    command,
    draft_campaign,
    end_request,
)
from .test_taskrun_postgresql import act, expire

pytestmark = pytest.mark.django_db(transaction=True)


def future_close(campaign):
    """Retained future work is real SQL data, not a fabricated admission callback."""
    with work_transaction():
        row = CampaignBoundaryOccurrence.objects.create(
            campaign=campaign,
            kind="close",
            due_at=campaign.active_configuration.ends_at,
        )
        task = enqueue(
            task_type="campaign_boundary",
            domain_request_id=campaign.pk,
            actor_id=None,
            correlation_id=uuid4(),
            idempotency_key=row.pk,
            admit=lambda *args: True,
        )
    return row, task


@pytest.mark.parametrize("state", ["queued", "running", "abandoned"])
def test_preflight_sees_root_claim_even_before_occurrence_binding(tmp_path, state):
    store, campaign, actor = draft_campaign(tmp_path)
    with campaign_clock(campaign.active_configuration.starts_at):
        command(campaign, actor, Action.ACTIVATE)
        row, task = future_close(campaign)
        if state != "queued":
            task = act(task, "claim", lease_seconds=1 if state == "abandoned" else 300)
        if state == "abandoned":
            task = expire(task)
        assert row.task_id is None
        assert close_work_running(campaign.pk) is (state != "queued")
        request, _ = end_request(store, campaign, actor, "edit_end")
        previous = store.active()
        if state == "queued":
            result = install_request(
                store,
                request_id=request.request_id,
                correlation_id=uuid4(),
                admit_campaign=admit_test_work,
            )
            assert result.state == "applied"
            row.refresh_from_db()
            assert row.state == "skipped" and row.reason == "boundary_replaced"
        else:
            with pytest.raises(CampaignAdmissionUnavailable):
                install_request(
                    store,
                    request_id=request.request_id,
                    correlation_id=uuid4(),
                    admit_campaign=admit_test_work,
                )
            assert store.active() == previous
