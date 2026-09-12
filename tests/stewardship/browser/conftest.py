"""Serve actual shared templates/assets locally; never contact a real provider."""

import os
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string

from parishkit.stewardship.accounts.campaign_forms import CampaignForm
from parishkit.stewardship.accounts.parish_views import ParishForm
from parishkit.stewardship.accounts.share_forms import (
    ShareOptions,
    default_share_options,
)
from parishkit.stewardship.campaigns.domain import Percentage
from parishkit.stewardship.web.security import CSP

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def browser_opt_in():
    """Skip before any browser, HTTP-server or npm-asset fixture is evaluated."""
    if os.environ.get("PARISHKIT_RUN_BROWSER_TESTS") != "1":
        pytest.skip("Browser component tests require PARISHKIT_RUN_BROWSER_TESTS=1.")


@pytest.fixture(scope="module")
def browser_engine(request):
    """An explicitly enabled browser job fails if tools/engines are missing."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as runner:
        browser = getattr(runner, request.param).launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser_engine):
    """Each scenario has isolated browser state and an explicit non-parish zone."""
    context = browser_engine.new_context(
        timezone_id="America/Los_Angeles", reduced_motion="reduce"
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def component_origin():
    """An exact response allowlist avoids exposing source files through the server."""
    context = {
        "server_now": NOW,
        "deadline": NOW + timedelta(hours=1),
        "absolute_deadline": NOW + timedelta(hours=4),
        "csrf_token": "a" * 64,
    }
    admin = {
        "admin": True,
        "parish_name": "Sample Parish",
        "navigation": [
            {"url": "/home", "label": "Home"},
            {"url": "/parish-settings", "label": "Parish settings"},
            {"url": "/ministries", "label": "Ministry activity"},
        ],
        "testing": True,
        "testing_recipient": "testing@example.org",
        "background": {"total": 1, "running": 1},
        "server_now": NOW,
        "idle_deadline": NOW + timedelta(hours=1),
        "absolute_deadline": NOW + timedelta(hours=12),
    }
    ministry = {
        "duid": 12345,
        "name": "Community outreach",
        "active": True,
        "included": True,
    }
    responses = {
        "/login": ("text/html", render_to_string("stewardship/login.html", context)),
        "/family-login": (
            "text/html",
            render_to_string("stewardship/family-login.html", context),
        ),
        "/family": ("text/html", render_to_string("stewardship/family.html", context)),
        "/errors": (
            "text/html",
            render_to_string(
                "stewardship/family-login.html",
                {
                    **context,
                    "errors": [
                        {"field_id": "family-code", "message": "Check the Family code."}
                    ],
                },
            ),
        ),
    }
    for path, template, extra in (
        (
            "/home",
            "home",
            {"configuration": {"mode": "testing"}, "admin_chrome": admin},
        ),
        (
            "/codes",
            "codes",
            {
                "table_caption": "Active Families",
                "table_headings": ["Family DUID", "Code"],
                "table_rows": [["1234567890123456789", "ABCDEFGH"]],
                "page": 2,
                "size": 50,
                "has_next": True,
                "previous_page": 1,
                "next_page": 3,
            },
        ),
        ("/availability", "availability", {"setup": True, "admin": True}),
        ("/denied", "denied", {"retry_path": "/admin/login"}),
    ):
        responses[path] = (
            "text/html",
            render_to_string(f"stewardship/{template}.html", {**context, **extra}),
        )
    for path, template, extra in (
        (
            "/background-task",
            "background-task",
            {
                "task": {
                    "id": uuid4(),
                    "type": "source_refresh",
                    "state": "running",
                    "active": True,
                    "created_at": NOW.isoformat(),
                    "attempt": 1,
                    "retry_sequence": 0,
                    "progress": {
                        "phase": "fetching",
                        "current": 1000,
                        "total": 4000,
                        "display": Percentage(1000, 4000),
                    },
                },
                "work": {
                    "events": [
                        {
                            "version": 2,
                            "at": NOW.isoformat(),
                            "action": "progress",
                            "state": "running",
                            "progress": {
                                "phase": "fetching",
                                "current": 1000,
                                "total": 4000,
                                "display": Percentage(1000, 4000),
                            },
                        }
                    ]
                },
            },
        ),
        (
            "/presence",
            "presence",
            {
                "presence": {
                    "count": 1,
                    "as_of": NOW,
                    "sessions": [
                        {
                            "name": "Sample Family",
                            "duid": 12345,
                            "started_at": NOW,
                            "last_activity_at": NOW,
                            "presence_at": NOW,
                            "section": "welcome",
                        }
                    ],
                }
            },
        ),
        (
            "/share-settings",
            "share-settings",
            {
                "campaign": {
                    "pk": uuid4(),
                    "active_configuration": {"name": "Sample campaign"},
                },
                "base_digest": "a" * 64,
                "formset": ShareOptions(
                    prefix="options", previous=default_share_options()
                ),
            },
        ),
        (
            "/share-preview",
            "share-preview",
            {
                "campaign": {"pk": uuid4()},
                "preview": "synthetic-signed-intent",
                "before": [],
                "after": default_share_options(),
            },
        ),
        (
            "/campaign-settings",
            "campaign-settings",
            {
                "editable": True,
                "form": CampaignForm(
                    initial={
                        "name": "Sample campaign",
                        "timezone": "America/New_York",
                        "start_date": "2026-10-01",
                        "end_date": "2026-10-31",
                        "census": True,
                        "base_digest": "a" * 64,
                    },
                    ministries=[("4", "Community outreach")],
                    funds=[("9", "Offertory")],
                ),
            },
        ),
        (
            "/campaign-preview",
            "campaign-preview",
            {
                "creating": True,
                "preview": "synthetic-signed-intent",
                "changes": [
                    {
                        "label": "Campaign timezone",
                        "before": None,
                        "after": "America/New_York",
                    }
                ],
            },
        ),
        ("/ministries", "ministries", {"ministries": [ministry], "state": "all"}),
        (
            "/ministry-preview",
            "ministry-preview",
            {
                "ministry": ministry,
                "new_active": False,
                "preview": "synthetic-signed-intent",
                "seeded_count": 2,
                "manual_count": 1,
            },
        ),
        (
            "/parish-settings",
            "parish-settings",
            {
                "configuration": {
                    "mode": "testing",
                    "testing_recipient": "testing@example.org",
                },
                "form": ParishForm(
                    initial={
                        "name": "Sample Parish",
                        "website": "https://example.org",
                        "timezone": "America/New_York",
                        "phone": "+12125551234",
                        "base_digest": "a" * 64,
                    }
                ),
            },
        ),
        (
            "/parish-preview",
            "parish-preview",
            {
                "changes": [
                    {
                        "label": "Parish timezone",
                        "before": "America/New_York",
                        "after": "America/Los_Angeles",
                    }
                ],
                "timezone_changed": True,
                "preview": "synthetic-signed-intent",
            },
        ),
        (
            "/configuration-request",
            "configuration-request",
            {
                "receipt": {"state": "staged", "request_id": uuid4()},
            },
        ),
        (
            "/background",
            "background",
            {
                "work": {
                    "counts": {
                        "active": 1,
                        "queued": 0,
                        "retry_wait": 0,
                        "abandoned": 0,
                    },
                    "tasks": [
                        {
                            "id": str(uuid4()),
                            "type": "source_refresh",
                            "state": "running",
                            "heartbeat_at": NOW.isoformat(),
                            "progress": {
                                "phase": "fetching",
                                "current": 1000,
                                "total": 3000,
                                "display": Percentage(1000, 3000),
                            },
                        }
                    ],
                },
                "states": ("nonterminal", "all", "succeeded", "failed"),
                "selected_state": "nonterminal",
            },
        ),
    ):
        responses[path] = (
            "text/html",
            render_to_string(
                f"stewardship/{template}.html",
                context | {"admin_chrome": admin} | extra,
            ),
        )
    for name, kind in (("css", "text/css"), ("js", "application/javascript")):
        asset = f"stewardship/ui-v1.{name}"
        located = finders.find(asset)
        assert located is not None, f"Required component asset is missing: {asset}"
        responses[f"/static/{asset}"] = (kind, Path(located).read_text())

    class Handler(BaseHTTPRequestHandler):
        """Suppress raw request logging; unknown routes are intentionally empty."""

        def do_GET(self):
            """Serve only exact pre-rendered component fixtures with actual CSP."""
            kind, body = responses.get(self.path, ("text/plain", ""))
            self.send_response(200 if self.path in responses else 404)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            """Fixture HTTP traffic must not generate private request diagnostics."""

        def do_POST(self):
            """Fixtures never issue external redirects, even to synthetic identities."""
            self.send_response(405)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def axe_source():
    """Pinned test-only accessibility scanner, not a browser-delivered dependency."""
    path = Path(__file__).parent / "node_modules/axe-core/axe.min.js"
    assert path.is_file(), "Run npm ci --prefix tests/stewardship/browser."
    return path.read_text()
