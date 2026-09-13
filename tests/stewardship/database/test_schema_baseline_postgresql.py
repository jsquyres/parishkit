"""Fresh schema preserves the independently captured pre-consolidation contract."""

import hashlib
import json
from pathlib import Path

import pytest
from django.db import connection

from parishkit.stewardship.schema_inventory import inventory


@pytest.mark.django_db(transaction=True)
def test_fresh_schema_matches_verified_baseline():
    """Check every catalog object, including manually named indexes and SQL guards.

    The fixture was captured only after comparing an empty old-history database
    with a fresh baseline. It is not generated during tests. PostgreSQL's pinned
    major version matters to its catalog deparser; see the schema guide before
    intentionally changing this fingerprint.
    """
    expected = json.loads(Path(__file__).with_name("schema-baseline.json").read_text())
    actual = {
        kind: {
            "count": len(objects),
            "sha256": hashlib.sha256(
                json.dumps(objects, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
        for kind, objects in inventory(connection).items()
    }
    assert actual == expected
