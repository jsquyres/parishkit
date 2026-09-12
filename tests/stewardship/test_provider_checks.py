"""Provider checks use synthetic HTTP/SMTP and disposable private-pipe helpers."""

import base64
import io
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from parishkit.stewardship import provider_check_worker as worker
from parishkit.stewardship import provider_checks as parent
from parishkit.stewardship.accounts.credential_errors import (
    CredentialValidationUnavailable,
)

WORKSPACE = {
    "delegated_email": "mail@example.org",
    "sender": "mail@example.org",
    "reply_to": "staff@example.org",
    "recipient": "test@example.org",
}


def payload(target="slack", **overrides):
    """The candidate is deliberately fake; normal CI never contacts a provider."""
    settings = {
        "slack": {"channel_id": "C123"},
        "parishsoft": {"organization_id": 123},
        "google_workspace": WORKSPACE,
    }[target]
    return json.dumps(
        dict(
            target=target,
            settings=settings,
            candidate=base64.b64encode(b"synthetic-private").decode(),
        )
        | overrides
    ).encode()


class Response:
    """Track a finite fake streamed response, including closure on error."""

    def __init__(self, status=200, body=b'{"ok":true}'):
        self.status_code, self.body = status, body
        self.headers = {"content-type": "application/json"}
        self.closed = self.read = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        """Keep the real byte-bound code, replacing only external network IO."""
        self.read = True
        yield self.body


def http(monkeypatch, response):
    """Patch the parent Requests implementation, preserving the restricted session."""
    calls = []

    def request(session, method, url, **kwargs):
        """Capture fixed transport options without actually opening a socket."""
        assert session.trust_env is False
        calls.append((method, url, kwargs, dict(session.headers)))
        return response

    monkeypatch.setattr(requests.Session, "request", request)
    return calls


def test_slack_auth_check_has_no_delivery_or_channel_read(monkeypatch):
    """Authentication needs no extra channel-read scope and cannot post a message."""
    response = Response()
    calls = http(monkeypatch, response)
    assert worker.check_request(payload()) == "valid"
    assert len(calls) == 1
    method, url, options, _ = calls[0]
    assert (method, url) == ("POST", "https://slack.com/api/auth.test")
    assert options == {
        "headers": {"Authorization": "Bearer synthetic-private"},
        "data": {},
        "timeout": 10,
        "stream": True,
        "allow_redirects": False,
    }
    assert response.closed


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b'{"ok":false,"error":"invalid_auth"}', "invalid"),
        (b'{"ok":false,"error":"ratelimited"}', "unavailable"),
        (b'{"ok":false,"error":"internal_error"}', "unavailable"),
        (b'{"ok":false,"error":"service_unavailable"}', "unavailable"),
        (b'{"ok":"true"}', "invalid"),
        (b"[]", "invalid"),
        (b'{"ok":false,"ok":true}', "invalid"),
        (b"private-invalid-json", "invalid"),
    ],
)
def test_slack_classification_is_closed(monkeypatch, body, expected):
    """Provider bodies never become diagnostics or a truthy success shortcut."""
    http(monkeypatch, Response(body=body))
    assert worker.check_request(payload()) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (301, "invalid"),
        (307, "invalid"),
        (401, "invalid"),
        (429, "unavailable"),
        (500, "unavailable"),
        (503, "unavailable"),
    ],
)
def test_http_failures_are_bounded_and_classified(monkeypatch, status, expected):
    """A redirect is never followed; an outage does not reject the credential."""
    response = Response(status=status)
    http(monkeypatch, response)
    assert worker.check_request(payload()) == expected
    assert response.closed
    if status >= 429 or status < 400:
        assert not response.read


def test_response_size_bound_and_no_arbitrary_origins(monkeypatch):
    """A huge successful response fails before JSON parsing or credential success."""
    response = Response(body=b"x" * (worker.MAX_RESPONSE + 1))
    calls = http(monkeypatch, response)
    assert worker.check_request(payload()) == "invalid" and response.closed
    with worker.CheckSession() as session:
        for method, url, options in [
            ("GET", "https://slack.com/api/auth.test", {}),
            ("POST", "https://evil.example", {}),
            ("POST", "https://slack.com/api/chat.postMessage", {}),
            ("POST", "https://slack.com/api/auth.test", {"proxies": {}}),
        ]:
            with pytest.raises(ValueError):
                session.request(method, url, **options)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b'[{"organizationID":123}]', "valid"),
        (b'[{"organizationID":124}]', "invalid"),
        (b'[{"organizationID":123},{"organizationID":124}]', "invalid"),
        (b'[{"organizationID":"123"}]', "invalid"),
        (b"[]", "invalid"),
    ],
)
def test_shared_parishsoft_client_checks_exact_uncached_tenant(
    monkeypatch, body, expected, tmp_path
):
    """No full source load, writes, cache directory or unscoped second request."""
    monkeypatch.chdir(tmp_path)
    calls = http(monkeypatch, Response(body=body))
    assert worker.check_request(payload("parishsoft")) == expected
    assert len(calls) == 1
    assert calls[0][1] == worker.DEFAULT_API_BASE_URL + "/organizations/search"
    assert calls[0][3]["x-api-key"] == "synthetic-private"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("greeting", "auth", "expected"),
    [
        (250, 235, "valid"),
        (250, 535, "invalid"),
        (250, 454, "unavailable"),
        (500, 235, "invalid"),
    ],
)
def test_workspace_token_and_smtp_authentication_never_send(
    monkeypatch, greeting, auth, expected
):
    """Reuse shared credential construction/XOAUTH2 with a fixed Google endpoint."""
    calls = http(monkeypatch, Response(body=b'{"access_token":"synthetic-token"}'))
    refreshes = []

    def refresh(request):
        """Exercise the Google transport interface without using a signing key."""
        response = request(
            worker.GOOGLE_TOKEN_URI, method="POST", body=b"signed-jwt", headers={}
        )
        refreshes.append(response.status)
        with pytest.raises(ValueError):
            request("https://evil.example", method="POST")

    credentials = SimpleNamespace(token="synthetic-token", refresh=refresh)
    factory = Mock(return_value=credentials)
    monkeypatch.setattr(worker, "workspace_candidate", factory)
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(return_value=None)
    smtp.ehlo.return_value = greeting, b"private-response"
    smtp.docmd.return_value = auth, b"private-response"
    smtp_factory = Mock(return_value=smtp)
    monkeypatch.setattr(worker.smtplib, "SMTP_SSL", smtp_factory)
    assert worker.check_request(payload("google_workspace")) == expected
    factory.assert_called_once_with(
        b"synthetic-private", delegated_email="mail@example.org"
    )
    assert refreshes == [200] and len(calls) == 1
    assert smtp_factory.call_args.args == ("smtp.gmail.com", 465)
    assert smtp_factory.call_args.kwargs["timeout"] == 10
    smtp.send_message.assert_not_called()
    smtp.sendmail.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"private-invalid-json",
        b'{"target":"slack","target":"parishsoft"}',
        payload(candidate="not-base64!"),
        payload(candidate=""),
        payload(settings={}),
        payload(extra="private"),
        b"x" * (worker.MAX_INPUT + 1),
    ],
)
def test_invalid_ipc_never_starts_provider_io(monkeypatch, raw):
    """Malformed or oversized input becomes a fixed outcome, with no echo."""
    network = Mock(side_effect=AssertionError("network must not run"))
    monkeypatch.setattr(worker, "CheckSession", network)
    assert worker.check_request(raw) == "invalid"
    network.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError("private"),
        requests.Timeout("private"),
        OSError("private"),
    ],
)
def test_transport_exceptions_have_safe_retry_outcome(monkeypatch, error):
    """Transient failures retain the sealed request for an ordinary bounded retry."""
    monkeypatch.setattr(requests.Session, "request", Mock(side_effect=error))
    assert worker.check_request(payload()) == "unavailable"


def test_worker_main_returns_only_closed_outcome(monkeypatch, capsys):
    """Malformed input is useful for a real subprocess check with no network access."""
    result = subprocess.run(
        [sys.executable, "-I", "-m", "parishkit.stewardship.provider_check_worker"],
        input=b"private-invalid-json",
        capture_output=True,
        timeout=10,
        env={},
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"invalid\n", b"")


class Process:
    """Model subprocess communication and finite reaping without sleeping."""

    def __init__(self, output=b"valid\n", returncode=0):
        self.stdout, self.stdin = io.BytesIO(), io.BytesIO()
        self.output, self.returncode = output, returncode
        self.inputs = []
        self.killed = False

    def communicate(self, *, input, timeout):
        """Only stdin may contain the synthetic secret."""
        self.inputs.append(input)
        return self.output, None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self, *, timeout):
        assert timeout == 5
        self.returncode = -9


def invoke(**changes):
    """Explicit internal owning check, separate from database admission tests."""
    return parent.check_candidate(
        "slack",
        {"channel_id": "C123"},
        b"synthetic-private",
        **(dict(seconds=30, check=lambda: None) | changes),
    )


@pytest.mark.parametrize(
    ("output", "code", "expected"),
    [
        (b"valid\n", 0, True),
        (b"invalid\n", 0, False),
        (b"unavailable\n", 0, None),
        (b"private\n", 0, None),
        (b"valid\n", 1, None),
        (b"valid\nextra", 0, None),
    ],
)
def test_parent_private_ipc_and_closed_output(monkeypatch, output, code, expected):
    """No inherited environment, SQL descriptors, stderr or private command args."""
    process = Process(output, code)
    factory = Mock(return_value=process)
    monkeypatch.setattr(parent.subprocess, "Popen", factory)
    if expected is None:
        with pytest.raises(CredentialValidationUnavailable):
            invoke()
    else:
        assert invoke() is expected
    args, options = factory.call_args
    assert args == (
        [sys.executable, "-I", "-m", "parishkit.stewardship.provider_check_worker"],
    )
    assert options == dict(
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        env={},
    )
    assert worker.decode_request(process.inputs[0])[2] == b"synthetic-private"
    assert process.stdin.closed and process.stdout.closed


def test_parent_timeout_reaps_child_and_never_resends_input(monkeypatch):
    """Repeated communicate calls retain stdin state; deadline always kills/reaps."""
    process = Process(returncode=None)

    def communicate(*, input, timeout):
        process.inputs.append(input)
        raise subprocess.TimeoutExpired("synthetic", timeout)

    process.communicate = communicate
    monkeypatch.setattr(parent.subprocess, "Popen", lambda *args, **kwargs: process)
    instants = iter([0, 0, 1, 31])
    monkeypatch.setattr(parent.time, "monotonic", lambda: next(instants))
    with pytest.raises(CredentialValidationUnavailable):
        invoke()
    assert len(process.inputs) == 2 and process.inputs[1] is None
    assert process.killed and process.returncode == -9
    assert process.stdin.closed and process.stdout.closed


def test_failed_drain_is_fatal(monkeypatch):
    """Unconfirmed drainage must escape ordinary installer exception/retry handling."""
    process = Process(returncode=None)
    process.wait = Mock(side_effect=subprocess.TimeoutExpired("synthetic", 5))
    monkeypatch.setattr(parent.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(parent.ProviderCheckDrainFailure):
        invoke()
    assert process.killed and process.stdin.closed


def test_lost_admission_starts_no_child(monkeypatch):
    """A closed startup interlock cannot launch even an authentication-only helper."""
    launch = Mock()
    monkeypatch.setattr(parent.subprocess, "Popen", launch)
    with pytest.raises(PermissionError):
        invoke(check=Mock(side_effect=PermissionError("denied")))
    launch.assert_not_called()


@pytest.mark.parametrize("seconds", [0, -1, 31, True, float("nan"), float("inf"), "30"])
def test_invalid_deadline_is_rejected_before_spawn(seconds):
    """No coercion, unbounded wait or NaN deadline can disable forced drainage."""
    with pytest.raises(ValueError):
        invoke(seconds=seconds)
