"""Exercise boundary production/execution using actual isolated runtime logins."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.models import F

from parishkit.stewardship.accounts.family_authentication import FamilyRuntime
from parishkit.stewardship.accounts.runtime_models import SystemConfiguration
from parishkit.stewardship.campaigns.boundary_production import produce_boundaries
from parishkit.stewardship.campaigns.boundary_tasks import boundary_handler
from parishkit.stewardship.campaigns.credential_models import (
    FamilyCampaign,
    FamilySession,
)
from parishkit.stewardship.campaigns.family_identity import code_context
from parishkit.stewardship.campaigns.lifecycle import Action
from parishkit.stewardship.campaigns.models import (
    Campaign,
    CampaignBoundaryOccurrence,
    CampaignTransition,
    RuntimeTransition,
)
from parishkit.stewardship.deployment import ServiceRole
from parishkit.stewardship.jobs.dispatch import WorkQueue, claim_hint
from parishkit.stewardship.jobs.lifetime import maintain_execution
from parishkit.stewardship.jobs.scheduler import scheduler_session

from .campaign_builders import add_draft, campaign_clock, command
from .credential_builders import family_campaign, keys, populate
from .test_background_grants_postgresql import task_login
from .test_boundary_production_postgresql import scheduled  # noqa: F401
from .test_boundary_tasks_postgresql import run
from .test_family_auth_postgresql import login

pytestmark = pytest.mark.django_db(transaction=True)


def test_runtime_scheduler_produces_and_worker_applies_ordered_boundaries(
    scheduled,  # noqa: F811
):
    """Production role names exercise initial-setup guard interactions too."""
    with campaign_clock(scheduled.active_configuration.ends_at):
        with (
            task_login(ServiceRole.SCHEDULER, exact=True),
            scheduler_session() as guard,
        ):
            start, close = produce_boundaries(guard)
        with task_login(ServiceRole.WORKER, exact=True):
            assert run(close)
            assert run(start)
    scheduled.refresh_from_db()
    assert scheduled.state == "closed"


@pytest.fixture
def populated(tmp_path):
    """Retain real token values so unauthorized SQL cannot pass on empty tables."""
    _, campaign, actor, _ = family_campaign(tmp_path)
    with campaign_clock(campaign.active_configuration.starts_at - timedelta(days=1)):
        command(campaign, actor, Action.ACTIVATE)
    return campaign


@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE stewardship_campaign SET state='active', version=version+1",
        "UPDATE stewardship_family_token SET digest=NULL, version=version+1",
        "UPDATE stewardship_family_token SET ciphertext=NULL, digest=NULL, "
        "destroyed_at=stewardship_campaign_now_v1(), version=version+1",
        "UPDATE stewardship_family_token_generation SET state='superseded', "
        "version=version+1",
    ],
)
def test_worker_cannot_mutate_populated_boundary_state_without_claim(
    populated, exact, statement
):
    """Neither installed nor custom worker names can change lifecycle or credentials."""
    with (
        campaign_clock(populated.active_configuration.ends_at),
        task_login(ServiceRole.WORKER, exact=exact),
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(statement)
    populated.refresh_from_db()
    assert populated.state == "scheduled"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM stewardship_family_token WHERE digest IS NOT NULL"
        )
        assert cursor.fetchone()[0] == 1


def test_worker_close_scrubs_real_tokens_and_revokes_authenticated_family(
    auth_service, settings
):
    """The close path destroys credentials without needing permission to read them."""
    actor = uuid4()
    _, row, _ = add_draft(auth_service.store, auth_service.store.active(), actor)
    campaign = Campaign.objects.get(pk=UUID(row["id"]))
    ring = keys()
    populate(campaign, ring)
    settings.STEWARDSHIP_FAMILY_RUNTIME = FamilyRuntime(
        auth_service.store, auth_service.limiter, ring.general, ring.mac, ring.public
    )
    family = FamilyCampaign.objects.get()
    code = ring.general.decrypt(
        family.code_ciphertext, context=code_context(family.pk)
    ).decode()
    with campaign_clock(campaign.active_configuration.starts_at - timedelta(days=1)):
        command(campaign, actor, Action.ACTIVATE)
    with campaign_clock(campaign.active_configuration.starts_at):
        with (
            task_login(ServiceRole.SCHEDULER, exact=True),
            scheduler_session() as guard,
        ):
            (start,) = produce_boundaries(guard)
        with task_login(ServiceRole.WORKER, exact=True):
            assert run(start)
        browser, response = login(code)
        assert response.status_code == 302
        assert FamilySession.objects.get().revoked_at is None
    with campaign_clock(campaign.active_configuration.ends_at):
        with (
            task_login(ServiceRole.SCHEDULER, exact=True),
            scheduler_session() as guard,
        ):
            (close,) = produce_boundaries(guard)
        with task_login(ServiceRole.WORKER, exact=True):
            assert run(close)
        assert browser.get("/family/").status_code == 302
    assert (
        FamilySession.objects.get().revoked_at == campaign.active_configuration.ends_at
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ciphertext, digest, destroyed_at FROM stewardship_family_token"
        )
        assert cursor.fetchone() == (None, None, campaign.active_configuration.ends_at)


@pytest.mark.parametrize("exact", [False, True])
def test_worker_cannot_return_archived_campaign_to_testing(scheduled, exact):  # noqa: F811
    """Custom role names must not bypass the worker-only runtime transition guard."""
    with campaign_clock(scheduled.active_configuration.ends_at):
        with scheduler_session() as guard:
            start, close = produce_boundaries(guard)
        assert run(close) and run(start)
        command(scheduled, uuid4(), Action.ARCHIVE)
        runtime = SystemConfiguration.objects.get()
        with (
            task_login(ServiceRole.WORKER, exact=exact),
            pytest.raises(DatabaseError),
            transaction.atomic(),
        ):
            RuntimeTransition.objects.create(
                request_id=uuid4(),
                expected_version=runtime.version,
                action="return_testing",
                before_mode=runtime.mode,
                after_mode="testing",
                before_campaign_id=scheduled.pk,
                after_campaign_id=None,
                actor_id=uuid4(),
                correlation_id=uuid4(),
            )
        runtime.refresh_from_db()
        assert (
            runtime.mode == "production" and runtime.current_campaign_id == scheduled.pk
        )


@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize(
    "field", ["pending_reason", "reason", "token_generation_id", "prior_projection_id"]
)
def test_live_worker_claim_does_not_allow_extra_boundary_metadata(
    scheduled,  # noqa: F811
    exact,
    field,
):
    """A real live claim still permits only the compiled boundary row shapes."""
    with campaign_clock(scheduled.active_configuration.starts_at):
        with scheduler_session() as guard:
            (start,) = produce_boundaries(guard)
        with task_login(ServiceRole.WORKER, exact=exact):
            execution = claim_hint(
                start.task_root_id,
                queue=WorkQueue.GENERAL,
                worker_id=uuid4(),
                handlers={"campaign_boundary": boundary_handler()},
            )
            with maintain_execution(execution), execution.effect():
                CampaignBoundaryOccurrence.objects.filter(
                    pk=start.occurrence_id
                ).update(
                    task_id=execution.claim.run_id,
                    task_fence=execution.claim.fence,
                    version=F("version") + 1,
                    actor_id=execution.claim.worker_id,
                    correlation_id=execution.correlation_id,
                )
                with pytest.raises(DatabaseError), transaction.atomic():
                    if field == "pending_reason":
                        CampaignBoundaryOccurrence.objects.filter(
                            pk=start.occurrence_id
                        ).update(
                            reason="boundary_replaced",
                            version=F("version") + 1,
                        )
                    else:
                        options = {
                            field: "private detail" if field == "reason" else uuid4()
                        }
                        current = Campaign.objects.get(pk=scheduled.pk)
                        runtime = SystemConfiguration.objects.get()
                        CampaignTransition.objects.create(
                            campaign=current,
                            action="start",
                            expected_version=current.version,
                            expected_runtime_version=runtime.version,
                            before_state=current.state,
                            after_state="active",
                            before_mode=runtime.mode,
                            after_mode=runtime.mode,
                            configuration_id=runtime.active_configuration_id,
                            request_id=uuid4(),
                            actor_id=execution.claim.worker_id,
                            correlation_id=execution.correlation_id,
                            boundary_id=start.occurrence_id,
                            task_fence=execution.claim.fence,
                            **options,
                        )
