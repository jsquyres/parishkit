"""Local service launch, redacted health probes, and safe synthetic provisioning."""

import os
import stat
import sys
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from parishkit.stewardship import services
from parishkit.stewardship.cli import main
from parishkit.stewardship.deployment import DeploymentProfile, ServiceRole


@pytest.mark.parametrize("profile", [None, *DeploymentProfile])
@pytest.mark.parametrize("role", [None, *ServiceRole])
def test_service_startup_is_explicit_and_fail_closed(
    profile, role, monkeypatch, capsys
):
    """Only the implemented development web identity can replace its process."""
    execute = Mock()
    monkeypatch.setattr(services.os, "execve", execute)
    assert services.run_service(profile, role) == 2
    if profile == "development" and role == "web":
        executable, arguments, environment = execute.call_args.args
        assert executable == sys.executable
        assert arguments == [
            sys.executable,
            "-m",
            "django",
            "runserver",
            "0.0.0.0:8000",
        ]
        assert environment["DJANGO_SETTINGS_MODULE"].endswith(".development")
        assert environment["PATH"] == os.environ["PATH"]
        assert not capsys.readouterr().err
    else:
        execute.assert_not_called()
        assert "startup refused" in capsys.readouterr().err


def test_service_cli(monkeypatch):
    """The installed CLI delegates rather than duplicating process behavior."""
    execute = Mock()
    monkeypatch.setattr(services.os, "execve", execute)
    assert main(["service", "--profile", "development", "--service-role", "web"]) == 2
    execute.assert_called_once()
    assert main(["service"]) == 2


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [(200, b"ok\n", 0), (200, b"no\n", 1), (200, b"ok\nx", 1), (503, b"ok\n", 1)],
)
def test_health_response(status, body, expected, monkeypatch, capsys):
    """Health uses bounded reads, bypasses ambient proxies, and prints no body."""
    response = Mock(status=status)
    response.read.return_value = body
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = context
    factory = Mock(return_value=opener)
    monkeypatch.setattr(services, "build_opener", factory)
    assert main(["healthcheck"]) == expected
    proxy, redirect = factory.call_args.args
    assert proxy.proxies == {}
    assert (
        redirect.redirect_request(None, None, 302, None, None, "http://remote") is None
    )
    request = opener.open.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:8000/health/live"
    assert opener.open.call_args.kwargs == {"timeout": 3}
    if status == 200:
        response.read.assert_called_once_with(4)
    else:
        response.read.assert_not_called()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("error", [URLError("private reason"), TimeoutError("secret")])
def test_health_errors_are_redacted(error, monkeypatch, capsys):
    """Network failure is an unhealthy exit code, never raw exception output."""
    opener = Mock()
    opener.open.side_effect = error
    monkeypatch.setattr(services, "build_opener", Mock(return_value=opener))
    assert services.healthcheck() == 1
    assert capsys.readouterr() == ("", "")


def test_new_development_tree_is_private_and_not_application_bootstrap(
    tmp_path, capsys
):
    """Provision only disposable storage and a random, never-printed DB password."""
    root = tmp_path / "local"
    assert main(["prepare-development", "--runtime-root", str(root)]) == 0
    password_file = root / "credentials/development-postgres-password"
    password = password_file.read_text()
    assert len(password.strip()) >= 32
    assert password.strip() not in capsys.readouterr().out
    assert list((root / "credentials").iterdir()) == [password_file]
    assert not list((root / "config").iterdir())
    for path in [root, *root.rglob("*")]:
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == (
                0o700 if path.is_dir() else 0o600
            )
    assert main(["prepare-development", "--runtime-root", str(root)]) == 2
    assert password_file.read_text() == password
    assert "no existing data was replaced" in capsys.readouterr().err


def test_development_provisioning_requires_explicit_new_target(tmp_path):
    """No default root writes, implicit parents, or symlink-target modifications."""
    with pytest.raises(SystemExit):
        main(["prepare-development"])
    assert (
        main(["prepare-development", "--runtime-root", str(tmp_path / "absent/child")])
        == 2
    )
    if os.name == "posix":
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)
        assert main(["prepare-development", "--runtime-root", str(link)]) == 2
        assert link.is_symlink()
