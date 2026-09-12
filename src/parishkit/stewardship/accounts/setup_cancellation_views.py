"""A closed original-login cancellation surface, including YAML selection gaps."""

from uuid import UUID

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from parishkit.stewardship.storage import StaleRecordError

from .admin_editing import error_response
from .authentication import runtime
from .setup_cancellation import cancel_finalizing_setup, cancellation_status
from .setup_views import ERRORS, _closed


@require_http_methods(["GET", "HEAD", "POST"])
def setup_cancellation(request):
    """No draft, credential or contact values are returned across this exception."""
    try:
        service = runtime()
        _closed(request, {"attempt"})
        if request.method == "POST":
            cancel_finalizing_setup(
                request, service, UUID(request.POST.get("attempt", ""))
            )
            response = HttpResponseRedirect("/admin/setup/cancel")
        else:
            status = cancellation_status(request, service)
            response = render(
                request, "stewardship/setup-cancel.html", {"attempt": status}
            )
            if cancellation_status(request, service) != status:
                raise StaleRecordError("Setup changed while rendering.")
        response["Cache-Control"] = "no-store"
        return response
    except ERRORS as error:
        return error_response(error)
