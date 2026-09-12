"""Initial-setup attempt ownership; staging is never applied configuration.

Only opaque session/task identifiers and closed lifecycle metadata are retained
here. Session UUIDs deliberately are not foreign keys: expired login records can
be cleaned while setup's safe tombstone and audit references remain durable.
"""

from django.db import models

from parishkit.stewardship.storage import MutableRecord, UTCDateTimeField


class SetupAttempt(MutableRecord):
    """One deployment-wide attempt, permanently bound to one original Admin login."""

    immutable_fields = MutableRecord.immutable_fields + (
        "session_id",
        "owner_id",
        "base_id",
    )
    write_once_fields = ("source_task_id", "expired_at")
    session_id = models.UUIDField(unique=True)
    owner_id = models.UUIDField()
    base = models.ForeignKey("AppliedConfigurationVersion", on_delete=models.PROTECT)
    state = models.CharField(max_length=16, default="collecting")
    source_task = models.OneToOneField(
        "stewardship_jobs.TaskRun", null=True, on_delete=models.PROTECT
    )
    renewed_at = UTCDateTimeField(null=True)
    expired_at = UTCDateTimeField(null=True)
    expiry_reason = models.CharField(max_length=16, default="")

    class Meta(MutableRecord.Meta):
        db_table = "stewardship_setup_attempt"
        constraints = MutableRecord.Meta.constraints + [
            models.UniqueConstraint(
                models.Value(1),
                condition=models.Q(state__in=["collecting", "loading", "frozen"]),
                name="setup_one_pending_attempt",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    state__in=[
                        "collecting",
                        "loading",
                        "frozen",
                        "completed",
                        "expired",
                    ]
                ),
                name="setup_known_state",
            ),
            models.CheckConstraint(
                condition=~models.Q(state="loading")
                | models.Q(source_task__isnull=False),
                name="setup_loading_task",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    state="expired",
                    expired_at__isnull=False,
                    expiry_reason__in=[
                        "cancelled",
                        "session",
                        "idle",
                        "watchdog",
                        "absolute",
                    ],
                )
                | (
                    ~models.Q(state="expired")
                    & models.Q(expired_at__isnull=True, expiry_reason="")
                ),
                name="setup_expiry_shape",
            ),
        ]
