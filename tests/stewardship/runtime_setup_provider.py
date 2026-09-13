"""Synthetic external responses inside actual disposable runtime service owners."""

import json
import sys


def main():
    """Replace only network boundaries; keep CLI, grants, journals and leases real."""
    from parishkit import parishsoft_transport
    from parishkit.stewardship import provider_checks, readiness_delivery_process
    from parishkit.stewardship.readiness_delivery import DeliveryOutcome

    pages = json.loads(sys.argv.pop(1))
    responses = iter(())

    def exchange(payload, *, seconds, check):
        """Restart the finite fixture for each independently validated full load."""
        nonlocal responses
        check()
        request = json.loads(payload)
        if request["url"].rstrip("/").endswith("organizations/search"):
            responses = iter(pages)
        result = next(responses)
        check()
        return b"200\n" + json.dumps(result).encode()

    def validate(target, settings, value, *, seconds, check):
        """The installed target owner still admits its exact candidate and context."""
        check()
        assert target in {"parishsoft", "google_workspace"}
        assert value and seconds > 0
        return True

    def send(value, settings, mail, *, seconds, check):
        """Provider acceptance is synthetic; persisted submission ownership is not."""
        check()
        assert value and seconds > 0
        assert mail.recipient == settings["recipient"] == "testing@example.org"
        assert "TEST" in mail.message()["Subject"]
        check()
        return DeliveryOutcome.ACCEPTED

    parishsoft_transport._exchange = exchange
    provider_checks.check_candidate = validate
    readiness_delivery_process.submit_sample = send
    from parishkit.stewardship.cli import main as cli

    cli(sys.argv[1:])


if __name__ == "__main__":
    main()
