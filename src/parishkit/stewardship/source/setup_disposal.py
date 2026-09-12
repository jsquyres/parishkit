"""Bounded, exact-ownership removal of expired setup source payloads."""

from django.db import connection
from django.db.models import Exists, OuterRef

from parishkit.stewardship.accounts.setup_models import SetupAttempt
from parishkit.stewardship.campaigns.work_locks import require_work_order
from parishkit.stewardship.jobs.ownership import lock_task_claim
from parishkit.stewardship.storage import StorageInvariantError

from .leases import verify_source
from .rejection import reject_snapshot
from .snapshot_models import SourceSnapshot
from .version_models import ENTITY_MODELS

TASK_TYPE = "setup_source_cleanup"


def owned_snapshots(attempt_id):
    """Only this expired attempt's original Task chain owns disposable staging."""
    attempt = SetupAttempt.objects.get(pk=attempt_id, state="expired")
    return SourceSnapshot.objects.filter(
        task__root_id=attempt.source_task_id,
        task__task_type="setup_source_load",
        task__domain_request_id=attempt.pk,
        state__in=("staging", "ready", "rejected"),
        generation=None,
    )


def dispose_batch(execution, claim):
    """Delete at most 500 memberships and their unshared payloads atomically.

    Payload deletion precedes membership deletion so each SQL guard can prove
    original ownership without a caller-supplied allowlist or broad orphan scan.
    Deferrable foreign keys still require every remaining reference to resolve
    at commit. Shared payloads survive until their last disposable reference.
    """
    require_work_order()
    task = lock_task_claim(execution.claim)
    verify_source(claim)
    if task.task_type != TASK_TYPE or claim.phase != "full":
        raise PermissionError("Source disposal requires its dedicated setup owner.")
    snapshots = owned_snapshots(task.domain_request_id).order_by("source_fence", "id")
    # Rejected manifests with no members are permanent safe receipts, not work.
    for candidate in snapshots:
        if candidate.state != "rejected" or any(
            membership.objects.filter(snapshot=candidate).exists()
            for _, membership in ENTITY_MODELS.values()
        ):
            snapshot = candidate
            break
    else:
        return None

    def admit(action, candidate):
        """The exact expired root and drained source fence cannot change mid-batch."""
        return (
            action == "reject"
            and owned_snapshots(task.domain_request_id).filter(pk=candidate.pk).exists()
        )

    snapshot = reject_snapshot(snapshot.pk, claim, admit=admit)
    for payload, membership in ENTITY_MODELS.values():
        rows = list(
            membership.objects.filter(snapshot=snapshot)
            .order_by("id")
            .values_list("id", "payload_id")[:500]
        )
        if not rows:
            continue
        identifiers, payload_ids = map(list, zip(*rows, strict=True))
        other = membership.objects.filter(payload_id=OuterRef("pk")).exclude(
            pk__in=identifiers
        )
        removable = list(
            payload.objects.filter(pk__in=payload_ids)
            .filter(~Exists(other))
            .values_list("pk", flat=True)
        )
        with connection.cursor() as cursor:
            if removable:
                table = connection.ops.quote_name(payload._meta.db_table)
                cursor.execute(f"DELETE FROM {table} WHERE id=ANY(%s)", [removable])
            table = connection.ops.quote_name(membership._meta.db_table)
            cursor.execute(f"DELETE FROM {table} WHERE id=ANY(%s)", [identifiers])
            if cursor.rowcount != len(identifiers):
                raise StorageInvariantError("Setup source cleanup batch changed.")
        verify_source(claim)
        return len(identifiers)
    return 0
