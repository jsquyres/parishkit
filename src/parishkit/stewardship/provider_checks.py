"""Target-owned provider validation with private IPC and finite helper lifetime."""

import base64
import json
import math
import subprocess
import sys
import time
from contextlib import suppress

from .accounts.credential_errors import CredentialValidationUnavailable
from .accounts.key_files import MAX_FILE_BYTES
from .accounts.provider_context import validated_context


class ProviderCheckDrainFailure(BaseException):
    """Exit the isolated installer if the OS cannot confirm helper termination."""


def _stop(process):
    """Kill and reap this exact child; never leave credential-bearing work detached."""
    if process.poll() is not None:
        return
    try:
        with suppress(ProcessLookupError):
            process.kill()
        process.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        raise ProviderCheckDrainFailure("Provider check could not drain.") from None


def check_candidate(target, settings, value, *, seconds, check):
    """Run only the compiled helper; no secret arguments, environment or temp files.

    This internal function has no authorization of its own. The request validator
    below admits the actual target login, closes SQL and reserves a deadline first.
    """
    settings = validated_context(target, settings)
    if (
        type(value) is not bytes
        or not 0 < len(value) <= MAX_FILE_BYTES
        or type(seconds) not in (int, float)
        or not math.isfinite(seconds)
        or not 0 < seconds <= 30
        or not callable(check)
    ):
        raise ValueError("Invalid provider check invocation.")
    payload = json.dumps(
        {
            "target": target,
            "settings": settings,
            "candidate": base64.b64encode(value).decode("ascii"),
        }
    ).encode()
    process = None
    check()
    deadline = time.monotonic() + seconds
    try:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "parishkit.stewardship.provider_check_worker",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env={},
            )
            pending = payload
            while True:
                check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CredentialValidationUnavailable()
                try:
                    output, _ = process.communicate(
                        input=pending, timeout=min(remaining, 0.25)
                    )
                    break
                except subprocess.TimeoutExpired:
                    pending = None
            check()
        except OSError:
            raise CredentialValidationUnavailable() from None
        if process.returncode != 0 or output not in {b"valid\n", b"invalid\n"}:
            raise CredentialValidationUnavailable()
        return output == b"valid\n"
    finally:
        if process is not None:
            try:
                _stop(process)
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()


def request_validator(target, *, check):
    """Bind an isolated runtime to immutable intake scope, not current YAML guesses."""
    if target not in {"parishsoft", "google_workspace", "slack"} or not callable(check):
        raise ValueError("Unsupported provider validation target.")

    def validate(identifier, value):
        """Read narrow target evidence and close SQL sockets before external IO."""
        from django.db import DatabaseError, connections

        from .accounts.credential_database import admit_installer_database
        from .accounts.provider_models import ProviderValidationContext
        from .accounts.secret_requests import _now

        check()
        try:
            admit_installer_database(target)
            context = (
                ProviderValidationContext.objects.select_related("request")
                .filter(request_id=identifier, target=target, request__state="testing")
                .first()
            )
            if context is None:
                raise CredentialValidationUnavailable()
            # Reserve forced drainage inside the immutable request's TTL. A retry
            # with insufficient time yields to the installer's ordinary expiry path.
            seconds = min(30, (context.request.expires_at - _now()).total_seconds() - 5)
            if seconds <= 0:
                raise CredentialValidationUnavailable()
            settings = validated_context(target, context.settings)
        except DatabaseError:
            raise CredentialValidationUnavailable() from None
        finally:
            connections.close_all()
        return check_candidate(target, settings, value, seconds=seconds, check=check)

    return validate
