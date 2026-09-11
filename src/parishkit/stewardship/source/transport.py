"""Bind finite shared HTTP reads to live task/source fences and closed SQL state."""

from django.db import connection, connections

from parishkit.parishsoft_transport import BoundedSourceSession
from parishkit.stewardship.jobs.dispatch import Execution
from parishkit.stewardship.storage import StorageInvariantError

from .leases import SourceClaim, reserve_source_request


def source_session(execution, claim):
    """Create a read transport for this exact execution and maintained source lease.

    The caller enters maintain_execution/maintain_source before using the Session.
    Each shared-client retry repeats admission and reserves its own read/drain
    deadline. Connection cleanup is thread-local and leaves the independent
    renewal thread free to heartbeat throughout the provider wait.
    """
    if (
        not isinstance(execution, Execution)
        or not isinstance(claim, SourceClaim)
        or (claim.task_id, claim.task_fence, claim.worker_id)
        != (execution.claim.run_id, execution.claim.fence, execution.claim.worker_id)
    ):
        raise ValueError("Source transport requires its exact owning execution.")

    def before_request(seconds):
        """Never close the caller's transaction or perform HTTP inside it."""
        if connection.in_atomic_block:
            raise StorageInvariantError("Source HTTP cannot run inside a transaction.")
        try:
            with execution.effect():
                if (
                    not execution.control.active
                    or execution.control.source_claim != claim
                ):
                    raise StorageInvariantError(
                        "Source HTTP requires maintained task/source ownership."
                    )
                reserve_source_request(
                    claim, timeout_seconds=seconds, safety_seconds=15
                )
        finally:
            connections.close_all()

    return BoundedSourceSession(before_request=before_request, check=execution.check)
