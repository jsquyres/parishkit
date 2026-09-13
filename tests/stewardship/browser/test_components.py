"""WCAG automated checks plus keyboard, mobile, timezone and activity behavior."""

import pytest

from .conftest import NOW

pytestmark = pytest.mark.parametrize(
    "browser_engine", ["chromium", "firefox", "webkit"], indirect=True
)


def test_csp_permits_the_fixed_google_form_destination(page, component_origin):
    """Check the allowed destination with first-request interception only.

    Interception may not see later requests in a redirect chain. No fixture
    sends such a redirect; the OAuth HTTP suite verifies its destination.
    """
    page.route(
        "https://accounts.google.com/**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="<h1>Synthetic Google sign-in</h1>",
        ),
    )
    page.goto(component_origin + "/login")
    page.locator("form").evaluate(
        "form => form.action = 'https://accounts.google.com/o/oauth2/v2/auth'"
    )
    page.get_by_role("button", name="Sign in with Google").click()
    page.wait_for_url("https://accounts.google.com/**")
    assert page.get_by_role("heading", name="Synthetic Google sign-in").is_visible()


def test_csp_blocks_an_unrelated_form_destination(page, component_origin):
    """The permitted Google origin must not imply arbitrary cross-origin posting."""
    requests = []

    def foreign(route):
        requests.append(route.request.url)
        route.fulfill(status=200, body="unexpected navigation")

    page.route("https://unrelated.example/**", foreign)
    page.goto(component_origin + "/login")
    page.evaluate("""() => {
        window.formViolations = [];
        document.addEventListener('securitypolicyviolation', event => {
            window.formViolations.push(event.effectiveDirective);
        });
    }""")
    page.locator("form").evaluate(
        "form => form.action = 'https://unrelated.example/collect'"
    )
    # Chromium schedules a navigation before CSP cancels it; do not wait for
    # that nonexistent navigation, but do wait for the actual violation event.
    page.get_by_role("button", name="Sign in with Google").click(no_wait_after=True)
    page.wait_for_function("() => window.formViolations.includes('form-action')")
    assert requests == []
    assert page.url == component_origin + "/login"


@pytest.mark.parametrize(
    "path",
    [
        "/login",
        "/family-login",
        "/family",
        "/errors",
        "/home",
        "/codes",
        "/availability",
        "/denied",
        "/ministries",
        "/ministry-preview",
        "/parish-settings",
        "/parish-preview",
        "/configuration-request",
        "/background",
        "/campaign-settings",
        "/campaign-preview",
        "/share-settings",
        "/share-preview",
        "/presence",
        "/background-task",
        "/content-settings",
        "/content-preview",
        "/content-history",
        "/schedule-settings",
        "/schedule-preview",
        "/clone-settings",
        "/clone-preview",
        "/integrations",
        "/integration-settings",
        "/integration-preview",
        "/credential-replace",
        "/credential-status",
        "/credential-selection",
        "/branding-settings",
        "/branding-preview",
    ],
)
@pytest.mark.parametrize("width", [320, 1280])
def test_components_accessible_and_responsive(
    page, component_origin, axe_source, path, width
):
    """Automated checks supplement, not replace, human screen-reader review."""
    page.set_viewport_size({"width": width, "height": 900})
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    page.goto(component_origin + path)
    if path in {"/branding-settings", "/branding-preview"}:
        assert page.locator(".branding-preview").evaluate_all(
            "images => images.length > 0 && images.every("
            "image => image.complete && image.naturalWidth > 0)"
        )
    assert not failures
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.evaluate(axe_source)
    violations = page.evaluate("""async () => (await axe.run(document, {
        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']}
    })).violations.map(({id, impact, nodes}) => ({
        id, impact, targets: nodes.map(n => n.target)
    }))""")
    assert violations == []


def test_skip_link_and_error_summary_focus(page, component_origin):
    """Keyboard users can reach the main landmark and exact failing field."""
    page.goto(component_origin + "/login")
    page.keyboard.press("Tab")
    assert page.locator(":focus").inner_text() == "Skip to content"
    page.keyboard.press("Enter")
    assert page.locator(":focus").get_attribute("id") == "main"
    page.goto(component_origin + "/errors")
    assert page.locator(":focus").get_attribute("data-error-summary") == ""
    page.get_by_role("link", name="Check the Family code.").click()
    assert page.locator(":focus").get_attribute("id") == "family-code"


def test_visual_content_editor_never_executes_source_or_pasted_markup(
    page, component_origin
):
    """Visual edits sync source; raw source waits for the server sanitizer."""
    page.goto(component_origin + "/content-settings")
    editor = page.locator("[data-content-editor]")
    assert editor.is_visible()
    editor.fill("A visual edit")
    assert "A visual edit" in page.locator('textarea[name="html"]').input_value()
    editor.evaluate("""node => {
        const range = document.createRange();
        range.selectNodeContents(
            document.createTreeWalker(node, NodeFilter.SHOW_TEXT).nextNode()
        );
        const selection = window.getSelection();
        selection.removeAllRanges(); selection.addRange(range);
    }""")
    page.get_by_role("button", name="Bold", exact=True).click()
    assert (
        "<strong>A visual edit</strong>"
        in page.locator('textarea[name="html"]').input_value()
    )
    page.locator("[data-html-source] summary").click()
    page.locator('textarea[name="html"]').fill(
        '<img src=x onerror="window.unsafe=true">'
    )
    assert not editor.is_visible()
    assert page.evaluate("window.unsafe === undefined")
    page.reload()
    editor = page.locator("[data-content-editor]")
    editor.evaluate("""node => {
        node.focus();
        const range = document.createRange(); range.selectNodeContents(node);
        const selection = window.getSelection();
        selection.removeAllRanges(); selection.addRange(range);
        // Firefox intentionally strips synthetic ClipboardEvent data. Exercise
        // the application's paste handler with an explicit read-only fixture.
        const event = new Event('paste', {bubbles: true, cancelable: true});
        Object.defineProperty(event, 'clipboardData', {value: {
            getData: type => type === 'text/plain' ? '<b>plain only</b>' :
                '<img src=x onerror="window.unsafe=true">'
        }});
        node.dispatchEvent(event);
    }""")
    assert editor.inner_text() == "<b>plain only</b>"
    assert editor.locator("img, b").count() == 0


def test_timestamp_and_passive_presence_never_keep_session_alive(
    page, component_origin
):
    """Advance the browser clock without sleeping or synthesizing user activity."""
    page.clock.install(time=NOW)
    attempts = []
    page.route(
        "**/family/keepalive",
        lambda route: (attempts.append(route.request), route.abort()),
    )
    page.goto(component_origin + "/family")
    assert "6:00 AM PDT" in page.locator("time").inner_text()
    page.clock.fast_forward(56 * 60 * 1000)
    assert page.locator("#session-warning").is_visible()
    assert attempts == []
    page.clock.fast_forward(5 * 60 * 1000)
    assert page.locator("#session-expired").is_visible()
    assert not page.locator("#session-warning").is_visible()
    assert attempts == []


def test_activity_keepalive_is_empty_csrf_protected_and_bounded(page, component_origin):
    """Editing claims no draft data; rejected keepalives do not renew the timer."""
    page.clock.install(time=NOW)
    attempts = []

    def reject(route):
        """Observe actual fetch bytes and deny the synthetic untrusted activity."""
        attempts.append(route.request)
        route.fulfill(status=403, body="Unavailable")

    page.route("**/family/keepalive", reject)
    page.goto(component_origin + "/family")
    page.keyboard.press("Tab")
    page.clock.fast_forward(6 * 60 * 1000)
    page.wait_for_function("document.readyState === 'complete'")
    assert len(attempts) == 1
    assert attempts[0].method == "POST" and not attempts[0].post_data
    assert attempts[0].headers["x-csrftoken"] == "a" * 64
    page.clock.fast_forward(60 * 60 * 1000)
    assert page.locator("#session-expired").is_visible()
    assert len(attempts) == 1


@pytest.mark.parametrize("failure", ["http", "transport"])
def test_failed_keepalive_retains_activity_for_a_bounded_retry(
    page, component_origin, failure
):
    """No additional keystroke is needed after one failed activity transmission."""
    page.clock.install(time=NOW)
    attempts = []

    def reply(route):
        """The second empty claim succeeds with a synthetic future deadline."""
        attempts.append(route.request)
        if len(attempts) == 1:
            if failure == "transport":
                route.abort("failed")
            else:
                route.fulfill(status=503, body="Unavailable")
        else:
            route.fulfill(json={"idle_deadline": "2026-09-10T14:00:00Z"})

    page.route("**/family/keepalive", reply)
    page.goto(component_origin + "/family")
    page.keyboard.press("Tab")
    page.clock.fast_forward(6 * 60 * 1000)
    page.wait_for_timeout(50)
    assert len(attempts) == 1
    page.clock.fast_forward(4 * 60 * 1000)
    page.wait_for_timeout(50)
    assert len(attempts) == 1  # Five minutes between attempts, even on failure.
    page.clock.fast_forward(2 * 60 * 1000)
    page.wait_for_timeout(50)
    assert len(attempts) == 2
    assert all(not request.post_data for request in attempts)


def test_admin_activity_never_uses_family_keepalive(page, component_origin):
    """The Admin clock warns and expires without renewing through Family endpoints."""
    page.clock.install(time=NOW)
    attempts = []
    page.route(
        "**/family/keepalive",
        lambda route: (attempts.append(route.request), route.abort()),
    )
    page.goto(component_origin + "/home")
    page.keyboard.press("Tab")
    page.clock.fast_forward(56 * 60 * 1000)
    assert page.locator("#session-warning").is_visible()
    page.clock.fast_forward(5 * 60 * 1000)
    assert page.locator("#session-expired").is_visible()
    assert attempts == []


def test_javascript_disabled_retains_admin_form_and_family_explanation(
    browser_engine, component_origin
):
    """No silent failure: Admin core forms stay ordinary POST, Family explains JS."""
    context = browser_engine.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(component_origin + "/login")
        assert page.get_by_role("button", name="Sign in with Google").is_visible()
        assert page.locator("form").get_attribute("method") == "post"
        page.goto(component_origin + "/family")
        assert page.locator("noscript").is_visible()
        assert "enable JavaScript" in page.locator("noscript").inner_text()
    finally:
        context.close()


def test_parish_editor_retains_native_form_validation_and_timezone_scope(
    page, component_origin
):
    """Profile forms retain native validation and prospective timezone guidance."""
    page.goto(component_origin + "/parish-settings")
    assert "Existing campaign timezones" in page.locator("main").inner_text()
    name = page.get_by_label("Parish name")
    name.fill("")
    assert not name.evaluate("field => field.checkValidity()")
    name.fill("A renamed parish")
    assert name.evaluate("field => field.checkValidity()")
    assert page.get_by_role("button", name="Preview changes").is_visible()


def test_ministry_preview_preserves_operational_indicators(page, component_origin):
    """Configuration pages do not replace the persistent Admin navigation/header."""
    for path in ("/ministries", "/ministry-preview", "/configuration-request"):
        page.goto(component_origin + path)
        assert page.locator("[data-background-indicator]").is_visible()
        assert page.get_by_role("complementary", name="Testing mode").is_visible()


def test_campaign_modules_hide_and_disable_unselected_fields(page, component_origin):
    """Conditional groups cannot accidentally post data from a disabled module."""
    page.goto(component_origin + "/campaign-settings")
    ministry = page.get_by_role("group", name="Ministry selections")
    financial = page.get_by_role("group", name="Financial periods and funds")
    assert not ministry.is_visible() and not financial.is_visible()
    page.get_by_label("Ministry stewardship").check()
    assert ministry.is_visible()
    assert page.get_by_label("Included Ministries").input_value() == "4"
    page.get_by_label("Financial stewardship").check()
    assert financial.is_visible()
    page.get_by_label("Upcoming financial period start").fill("2027-01-01")
    page.get_by_label("Financial stewardship").uncheck()
    posted = page.locator("[data-campaign-form]").evaluate(
        "form => Array.from(new FormData(form).keys())"
    )
    assert "financial_start" not in posted and "fund_duids" not in posted
    assert "ministry_duids" in posted


def test_campaign_modules_remain_usable_without_javascript(
    browser_engine, component_origin
):
    """Server validation remains available when progressive enhancement is absent."""
    context = browser_engine.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(component_origin + "/campaign-settings")
        assert page.get_by_role(
            "group", name="Financial periods and funds"
        ).is_visible()
        assert page.get_by_label("Upcoming financial period start").is_enabled()
        assert page.get_by_role("button", name="Preview changes").is_visible()
    finally:
        context.close()


def test_family_presence_is_visible_only_bounded_and_carries_no_answers(
    page, component_origin
):
    """Presence posts neither answers nor activity claims and stops after expiry."""
    page.clock.install(time=NOW)
    requests = []

    def observe(route):
        """Record the exact wire contract and finish its bounded passive request."""
        requests.append(route.request)
        route.fulfill(
            status=200, content_type="application/json", body='{"recorded":true}'
        )

    page.route("**/family/presence", observe)
    page.goto(component_origin + "/family")
    page.wait_for_load_state("networkidle")
    assert len(requests) == 1 and requests[0].post_data == "section=welcome"
    page.clock.fast_forward(29000)
    assert len(requests) == 1
    page.evaluate(
        "Object.defineProperty(document, 'hidden', {configurable:true, get:()=>true})"
    )
    page.clock.fast_forward(31000)
    assert len(requests) == 1
    page.evaluate(
        "Object.defineProperty(document, 'hidden', {configurable:true, get:()=>false})"
    )
    with page.expect_response("**/family/presence"):
        page.clock.fast_forward(30000)
    page.wait_for_load_state("networkidle")
    assert len(requests) == 2
    page.clock.fast_forward(5 * 60 * 60 * 1000)
    assert len(requests) == 2


def test_admin_presence_poll_is_passive_and_shows_service_failure(
    page, component_origin
):
    """Header polling is read-only and a failure is not represented as zero presence."""
    page.clock.install(time=NOW)
    requests = []

    def observe(route):
        """First return a count, then a retriable failure without private error text."""
        requests.append(route.request)
        route.fulfill(
            status=200 if len(requests) == 1 else 503,
            content_type="application/json",
            body='{"count":1234}',
        )

    page.route("**/admin/presence?format=count", observe)
    with page.expect_response("**/admin/presence?format=count"):
        page.goto(component_origin + "/home")
    page.wait_for_function(
        "() => document.querySelector('[data-presence-count]').textContent === '1,234'"
    )
    assert requests[0].method == "GET" and not requests[0].post_data
    with page.expect_response("**/admin/presence?format=count"):
        page.clock.fast_forward(30000)
    page.wait_for_function(
        "() => !document.querySelector('[data-presence-unavailable]').hidden"
    )
    assert page.locator("[data-presence-count]").inner_text() == "1,234"
