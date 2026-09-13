"""Admit isolated task processes before assembling their closed handler registry.

The general worker can read ParishSoft, seal new links and reconcile local source
effects. It cannot decrypt email links or run future delivery/publication tasks.
The scheduler has metadata-only handlers and no executable provider dependency.
"""

from dataclasses import dataclass, field
from threading import Event

from parishkit.config import ConfigError

from .accounts.cryptography import independent_keyrings
from .accounts.key_files import parse_keyring, read_private
from .deployment import ServiceRole


@dataclass(frozen=True)
class BackgroundRuntime:
    """Retain only admitted dependencies; private keys/transport stay out of repr."""

    broker: object = field(repr=False)
    handlers: dict = field(repr=False)
    receipts: dict = field(repr=False)
    store: object = field(repr=False)


def matching_authority(store):
    """Every queue pass/effect holds when YAML selection and SQL truth disagree."""
    from .accounts.runtime_models import SystemConfiguration

    selected = store.active()
    actual = SystemConfiguration.objects.values_list(
        "active_configuration_id", "active_configuration__digest"
    ).first()
    if selected is None or actual != (selected.version_id, selected.digest):
        raise ConfigError("Background configuration requires recovery.")
    if store.manifest_reference() != actual:
        raise ConfigError("Background configuration changed during admission.")


def bind_authority(handlers, store, *, heartbeat=None):
    """Preserve compiled execution while adding fresh file/SQL checks to admission."""
    from dataclasses import replace
    from functools import partial

    def admit(original, action, status):
        """Neither a queued UUID nor startup readiness survives a later mismatch."""
        matching_authority(store)
        return original(action, status)

    return {
        name: replace(handler, admit=partial(admit, handler.admit), pulse=heartbeat)
        for name, handler in handlers.items()
    }


def pre_delivery_suppressions(scope):
    """Testing has no live address refusals before the Phase 4 delivery owner.

    This is an explicit phase admission boundary, not a default success callback:
    Production source effects remain disabled until BG-06 wires durable provider
    suppressions. Testing messages use the single test recipient and cannot
    suppress real Family recipients.
    """
    from .campaigns.work_locks import require_work_order

    require_work_order()
    if scope.runtime.mode != "testing":
        raise ConfigError("Production refresh requires the delivery suppression owner.")
    return frozenset()


def scheduler_handlers():
    """Compiled metadata admission only; accidental provider/file execution refuses."""
    from .accounts.branding_cleanup import TASK_TYPE as BRANDING_CLEANUP
    from .accounts.branding_cleanup import cleanup_handler
    from .campaigns.work_locks import work_transaction
    from .jobs.dispatch import Handler
    from .jobs.queues import WorkQueue
    from .source.outcomes import admit_refresh_metadata, recovery_plan
    from .source.requests import TASK_TYPE

    def unavailable(execution):
        """A scheduler cannot become a provider worker by calling a registry value."""
        raise PermissionError("The scheduler cannot execute provider work.")

    return {
        BRANDING_CLEANUP: cleanup_handler(),
        TASK_TYPE: Handler(
            queue=WorkQueue.GENERAL,
            admit=admit_refresh_metadata,
            execute=unavailable,
            recover=recovery_plan,
            scope=work_transaction,
        ),
    }


def configure_background(configuration, *, stop, heartbeat):
    """Assemble in a fresh process only after kernel mounts and real SQL admission."""
    from .accounts.metrics_credentials import credential_receipt
    from .jobs.broker import build_broker
    from .operator_commands import configure_operator_database
    from .runtime_grants import admit_runtime_database
    from .runtime_web import admit_lifecycle_mounts
    from .service_boundaries import admit_online_service

    role = configuration.service_role
    if (
        role not in {ServiceRole.WORKER, ServiceRole.SCHEDULER}
        or not isinstance(stop, Event)
        or not callable(heartbeat)
    ):
        raise ConfigError("An isolated background process and stop event are required.")
    if admit_online_service(configuration) is not role:
        raise ConfigError("Background service admission differs from its profile.")
    admit_lifecycle_mounts(configuration)
    required = (
        {"general_encryption", "family_code_mac", "token_public", "parishsoft"}
        if role is ServiceRole.WORKER
        else {"token_public"}
    )
    if not required <= configuration.secrets.keys():
        raise ConfigError("Background credential mounts are incomplete.")
    loaded = {name: read_private(path) for name, path in configuration.secrets.items()}
    rings = {
        name: parse_keyring(loaded[name], name) for name in required - {"parishsoft"}
    }
    independent_keyrings(*rings.values())
    if role is ServiceRole.WORKER:
        from .source.credentials import SourceCredential

        SourceCredential(loaded["parishsoft"])
    try:
        password = (
            read_private(configuration.valkey.password_file)
            .decode("ascii")
            .removesuffix("\n")
        )
    except (TypeError, ValueError, UnicodeError):
        raise ConfigError("An individual broker credential is required.") from None
    configure_operator_database(configuration)
    admit_runtime_database(configuration)
    from django.db import connections

    from .accounts.authority import AuthorityStore
    from .accounts.configuration_installation import coherent_configuration
    from .accounts.configuration_schema import validate_sections

    store = AuthorityStore(configuration.paths["authority"], validate_sections)
    coherent_configuration(store)

    if role is ServiceRole.SCHEDULER:
        handlers = scheduler_handlers()
    else:
        from .accounts.branding_cleanup import TASK_TYPE as BRANDING_CLEANUP
        from .accounts.branding_cleanup import cleanup_handler
        from .source.effects import refresh_reconciler
        from .source.execution import refresh_handler
        from .source.requests import TASK_TYPE

        handlers = {
            BRANDING_CLEANUP: cleanup_handler(configuration.paths["media"]),
            TASK_TYPE: refresh_handler(
                credential_path=configuration.secrets["parishsoft"],
                reconcile=refresh_reconciler(
                    general=rings["general_encryption"],
                    mac=rings["family_code_mac"],
                    public=rings["token_public"],
                    suppressions=pre_delivery_suppressions,
                ),
            ),
        }
    handlers = bind_authority(handlers, store, heartbeat=heartbeat)
    broker = build_broker(
        endpoint=configuration.valkey,
        password=password,
        service=role,
        handlers=handlers,
        stop=stop,
    )
    connections.close_all()
    return BackgroundRuntime(
        broker,
        handlers,
        {name: credential_receipt(raw, name) for name, raw in loaded.items()},
        store,
    )
