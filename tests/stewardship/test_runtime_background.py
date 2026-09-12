"""Compiled background startup rejects missing dependencies before serving work."""

from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import pytest

from parishkit.config import ConfigError
from parishkit.stewardship import runtime_background as background
from parishkit.stewardship.deployment import ServiceRole

from .test_runtime_topology import configuration_at


@pytest.fixture
def admitted_configuration(tmp_path, monkeypatch):
    """Use real purpose-key files; substitute only kernel/SQL process admission."""
    from parishkit.stewardship.accounts.cryptography import (
        CodeMacKeyring,
        GeneralKeyring,
        Key,
        TokenPrivateKeyring,
    )
    from parishkit.stewardship.accounts.key_files import (
        serialize_keyring,
        write_private,
    )

    configuration = configuration_at(tmp_path)
    rings = SimpleNamespace(
        general=GeneralKeyring([Key("g1", "active", b"g" * 32)]),
        mac=CodeMacKeyring([Key("m1", "active", b"m" * 32)]),
        public=TokenPrivateKeyring([Key("t1", "active", b"t" * 32)]).public(),
    )
    secrets = {}
    for name, ring in (
        ("general_encryption", rings.general),
        ("family_code_mac", rings.mac),
        ("token_public", rings.public),
    ):
        secrets[name] = tmp_path / name
        write_private(secrets[name], serialize_keyring(ring))
    secrets["parishsoft"] = tmp_path / "parishsoft"
    write_private(secrets["parishsoft"], b"synthetic-private-api-key")
    write_private(configuration.valkey.password_file, b"synthetic-broker-key")
    calls = []
    monkeypatch.setattr(
        "parishkit.stewardship.service_boundaries.admit_online_service",
        lambda config: calls.append("mounts") or config.service_role,
    )
    for target, label in (
        ("runtime_web.admit_lifecycle_mounts", "lifecycle"),
        ("operator_commands.configure_operator_database", "django"),
        ("runtime_grants.admit_runtime_database", "grants"),
        ("accounts.configuration_installation.coherent_configuration", "coherence"),
    ):
        monkeypatch.setattr(
            "parishkit.stewardship." + target,
            lambda *args, label=label: calls.append(label),
        )
    return replace(
        configuration, service_role=ServiceRole.WORKER, secrets=secrets
    ), calls


@pytest.mark.parametrize("role", [ServiceRole.WORKER, ServiceRole.SCHEDULER])
def test_background_assembly_binds_exact_keys_role_and_closed_registry(
    admitted_configuration, role
):
    """Build a real lazy broker without provider sockets or ambient configuration."""
    from parishkit.stewardship.accounts.key_files import file_fingerprint

    configuration, calls = admitted_configuration
    if role is ServiceRole.SCHEDULER:
        configuration = replace(
            configuration,
            service_role=role,
            secrets={"token_public": configuration.secrets["token_public"]},
        )
    stop, pulse = Event(), lambda: None
    runtime = background.configure_background(configuration, stop=stop, heartbeat=pulse)
    try:
        assert calls == ["mounts", "lifecycle", "django", "grants", "coherence"]
        assert runtime.broker.service is role and runtime.broker.stop is stop
        assert set(runtime.handlers) == {"source_refresh"}
        assert runtime.handlers["source_refresh"].pulse is pulse
        assert set(runtime.receipts) == set(configuration.secrets)
        if role is ServiceRole.WORKER:
            assert runtime.receipts["parishsoft"] == file_fingerprint(
                b"synthetic-private-api-key"
            )
        assert "synthetic" not in repr(runtime)
    finally:
        runtime.broker.app.close()


@pytest.mark.parametrize("failure", ["missing_key", "malformed_key", "bad_broker"])
def test_incomplete_background_credentials_fail_before_database_or_broker(
    admitted_configuration, failure
):
    """Invalid local material never starts a process with reduced source effects."""
    from parishkit.stewardship.accounts.key_files import write_private

    configuration, calls = admitted_configuration
    if failure == "missing_key":
        configuration = replace(
            configuration,
            secrets={
                key: value
                for key, value in configuration.secrets.items()
                if key != "family_code_mac"
            },
        )
    else:
        path = (
            configuration.secrets["parishsoft"]
            if failure == "malformed_key"
            else configuration.valkey.password_file
        )
        write_private(
            path, b"bad\nprivate\nvalue" if failure == "malformed_key" else "é".encode()
        )
    with pytest.raises((ConfigError, ValueError)):
        background.configure_background(
            configuration, stop=Event(), heartbeat=lambda: None
        )
    assert "django" not in calls


@pytest.mark.parametrize("role", [ServiceRole.WEB, ServiceRole.CONFIG_INSTALLER])
def test_background_assembly_does_not_accept_other_profiles(tmp_path, role):
    """A role name cannot bypass its separately owned online startup boundary."""
    configuration = replace(configuration_at(tmp_path), service_role=role)
    with pytest.raises(ConfigError):
        background.configure_background(
            configuration, stop=Event(), heartbeat=lambda: None
        )


def test_scheduler_registry_is_metadata_only():
    """It contains one compiled type and refuses even direct execution attempts."""
    handlers = background.scheduler_handlers()
    assert set(handlers) == {"source_refresh"}
    with pytest.raises(PermissionError):
        handlers["source_refresh"].execute(None)


def test_bound_registry_rechecks_authority_before_domain_admission(monkeypatch):
    """Prior startup admission cannot replace a current configuration check."""
    calls = []
    original = background.scheduler_handlers()["source_refresh"]
    original = replace(original, admit=lambda *args: calls.append("domain") or True)
    store, pulse = object(), lambda: None
    monkeypatch.setattr(
        background, "matching_authority", lambda value: calls.append(value)
    )
    handler = background.bind_authority(
        {"source_refresh": original}, store, heartbeat=pulse
    )["source_refresh"]
    assert handler.admit("hint", None)
    assert calls == [store, "domain"] and handler.pulse is pulse
    assert original.pulse is None


@pytest.mark.parametrize("mode", ["testing", "production"])
def test_phase_two_suppression_boundary_never_silently_enables_production(
    monkeypatch, mode
):
    """BG-06 must wire real provider-refusal state before live delivery is enabled."""
    monkeypatch.setattr(
        "parishkit.stewardship.campaigns.work_locks.require_work_order", lambda: None
    )
    scope = SimpleNamespace(runtime=SimpleNamespace(mode=mode))
    if mode == "testing":
        assert background.pre_delivery_suppressions(scope) == frozenset()
    else:
        with pytest.raises(ConfigError):
            background.pre_delivery_suppressions(scope)
