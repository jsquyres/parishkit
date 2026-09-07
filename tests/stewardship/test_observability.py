"""ARC-02: redacted UTC JSONL, safe event context, and isolated correlations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from parishkit.stewardship.observability import (
    CorrelationMiddleware,
    Event,
    SafeJsonFormatter,
    correlation,
    emit,
)


@pytest.mark.parametrize(
    "level",
    [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL],
)
def test_events_keep_safe_context_and_utc(caplog, level):
    """All five levels serialize identifiers and explicit UTC without free text."""
    task_id = uuid4()
    with caplog.at_level(logging.DEBUG), correlation() as identifier:
        emit(Event.TASK_STARTED, level=level, task_id=task_id)
    payload = json.loads(SafeJsonFormatter().format(caplog.records[-1]))
    assert payload["message"] == "task_started"
    assert payload["level"] == logging.getLevelName(level)
    assert payload["extra"] == {
        "task_id": str(task_id),
        "correlation_id": str(identifier),
    }
    assert datetime.fromisoformat(payload["timestamp"]).utcoffset() == UTC.utcoffset(
        None
    )


def test_unstructured_errors_are_redacted_without_mutating_record():
    """Discard unsafe names, formatted args, exception text, stacks, and extras."""
    record = logging.LogRecord(
        "synthetic-secret",
        logging.ERROR,
        "sensitive/path",
        1,
        "token=%s",
        ("synthetic-secret",),
        None,
    )
    record.exc_text = "synthetic-secret"
    record.stack_info = "synthetic-secret"
    record.extra = {
        "correlation_id": "synthetic-secret",
        "task_id": None,
        "email": "synthetic-secret",
    }
    output = SafeJsonFormatter().format(record)
    assert "synthetic-secret" not in output and "sensitive/path" not in output
    assert json.loads(output)["message"] == "unstructured_log_suppressed"
    assert json.loads(output)["extra"] == {}
    assert record.getMessage() == "token=synthetic-secret"
    assert record.exc_text == "synthetic-secret"


@pytest.mark.parametrize("extra", [None, "synthetic-secret", ["synthetic-secret"]])
def test_unknown_extra_shapes_are_discarded(extra):
    """Unexpected third-party extras cannot bypass the strict context schema."""
    record = logging.LogRecord(
        "other", logging.INFO, "", 1, Event.CONFIG_REJECTED, (), None
    )
    record.extra = extra
    assert json.loads(SafeJsonFormatter().format(record))["extra"] == {}


def test_nested_correlations_restore_after_error(caplog):
    """Requests and tasks cannot inherit an earlier scope after it has exited."""
    with caplog.at_level(logging.INFO):
        with correlation() as outer:
            with pytest.raises(RuntimeError), correlation():
                raise RuntimeError("synthetic error")
            emit(Event.TASK_COMPLETED)
        emit(Event.TASK_COMPLETED)
    assert caplog.records[-2].extra["correlation_id"] == outer
    assert caplog.records[-1].extra["correlation_id"] is None


def test_invalid_event_inputs_are_rejected():
    """No arbitrary string event, severity, task ID, or correlation ID is allowed."""
    with pytest.raises(ValueError):
        emit("synthetic-secret")
    with pytest.raises(ValueError):
        emit(Event.TASK_STARTED, level=123)
    with pytest.raises(ValueError):
        emit(Event.TASK_STARTED, task_id="synthetic-secret")
    with pytest.raises(ValueError), correlation("synthetic-secret"):
        pass


def test_client_cannot_supply_correlation_id(client):
    """Requests get fresh internal IDs, not untrusted tracing-header values."""
    response = client.get("/", HTTP_X_CORRELATION_ID="synthetic-secret")
    identifier = UUID(response["X-Correlation-ID"])
    assert identifier != UUID(client.get("/")["X-Correlation-ID"])


def test_django_logging_cannot_bypass_redaction():
    """Default Django request/server handlers cannot retain raw path output."""
    for name in (
        "django",
        "django.server",
        "gunicorn.error",
        "gunicorn.access",
        "celery",
    ):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate


def test_middleware_restores_context_on_failure(caplog):
    """An uncaught handler failure must still release its per-request context."""

    def fail(request):
        """Inject a failure before a response is available."""
        raise RuntimeError("synthetic error")

    request = type("Request", (), {})()
    with pytest.raises(RuntimeError):
        CorrelationMiddleware(fail)(request)
    with caplog.at_level(logging.INFO):
        emit(Event.CONFIG_REJECTED)
    assert caplog.records[-1].extra["correlation_id"] is None
