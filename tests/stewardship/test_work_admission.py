"""Only compiled canonical work bindings reach the transactional admission layer."""

from uuid import uuid4

import pytest

from parishkit.stewardship.campaigns.domain import SystemMode
from parishkit.stewardship.campaigns.lifecycle import CampaignWorkKind
from parishkit.stewardship.jobs.admission import (
    require_campaign_work,
    require_source_refresh,
)


@pytest.mark.parametrize(
    "field,value",
    [
        ("campaign_id", None),
        ("campaign_id", "private-value"),
        ("kind", "preview"),
        ("kind", True),
        ("mode", "testing"),
        ("mode", True),
        ("rehearsal_epoch_id", "private-value"),
    ],
)
def test_uncanonical_campaign_binding_is_rejected_without_query(field, value):
    """Serialized flags cannot become handler-selected policy classifications."""
    options = dict(
        campaign_id=uuid4(),
        kind=CampaignWorkKind.PREVIEW,
        mode=SystemMode.TESTING,
    )
    with pytest.raises(TypeError) as error:
        require_campaign_work(**(options | {field: value}))
    assert "private-value" not in str(error.value)


def test_source_has_no_caller_selectable_maintenance_bypass():
    """Restricted restore exception workflows must have their own durable owner."""
    with pytest.raises(TypeError):
        require_source_refresh(campaign_id=None, maintenance=True)
    with pytest.raises(TypeError):
        require_source_refresh(campaign_id="not-a-uuid")
