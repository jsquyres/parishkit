"""Minimum task-runtime SQL authority; provider owners extend it explicitly.

The scheduler creates hints and can cancel superseded waiting source requests,
but cannot claim or impersonate running work. Workers can mutate fenced task
metadata, not campaign configuration, credentials or sessions. Id-only UPDATE
grants permit row locks; owning table guards reject an id-only mutation.
"""

from parishkit.config import ConfigError
from parishkit.stewardship.deployment import ServiceRole

READ_TABLES = frozenset(
    {
        "django_migrations",
        "stewardship_configuration_version",
        "stewardship_system_configuration",
        "stewardship_campaign",
        "stewardship_campaign_configuration",
        "stewardship_campaign_work_gate",
        "stewardship_campaign_credentials",
        "stewardship_rehearsal_epoch",
        "stewardship_activation_catchup",
        "stewardship_task_run",
        "stewardship_task_event",
    }
)


def task_runtime_grants(role):
    """Return new maps; neither a queue header nor caller mutation extends policy."""
    if role not in {ServiceRole.WORKER, ServiceRole.SCHEDULER}:
        raise ConfigError("This service has no general task SQL authority.")
    tables = {table: {"SELECT"} for table in READ_TABLES}
    tables["stewardship_task_run"].add("INSERT")
    tables["stewardship_task_event"].add("INSERT")
    for table in (
        "stewardship_audit_event",
        "stewardship_audit_context",
        "stewardship_operational_log",
    ):
        tables[table] = {"INSERT"}
    columns = {
        table: {"UPDATE": {"id"}}
        for table in (
            "stewardship_system_configuration",
            "stewardship_campaign",
            "stewardship_campaign_credentials",
        )
    }
    # Ownership triggers need only the parish identity/configuration binding.
    # Django INSERT RETURNING needs the declared database-default columns, not
    # read authority over unrelated historical audit or diagnostic payloads.
    columns.update(
        {
            "stewardship_parish": {"SELECT": {"id", "configuration_id"}},
            "stewardship_audit_event": {
                "SELECT": {"created_at", "ownership_scope", "parish_id"}
            },
            "stewardship_audit_context": {"SELECT": {"created_at"}},
            "stewardship_operational_log": {"SELECT": {"created_at"}},
        }
    )
    if role is ServiceRole.WORKER:
        tables["stewardship_task_run"].add("UPDATE")
        from parishkit.stewardship.source.grants import add_refresh_worker_grants

        add_refresh_worker_grants(tables, columns)
    else:
        from parishkit.stewardship.source.grants import add_refresh_scheduler_grants

        add_refresh_scheduler_grants(tables, columns)
    return tables, columns
