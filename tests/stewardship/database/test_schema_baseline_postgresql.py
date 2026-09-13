"""Fresh schema preserves the independently captured pre-consolidation contract."""

import hashlib
import json
from pathlib import Path

import pytest
from django.apps import apps
from django.db import connection, models

from parishkit.stewardship.campaigns.models import CampaignConfiguration
from parishkit.stewardship.schema_inventory import inventory

from .schema_contract import assert_model_contract


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


@pytest.mark.django_db(transaction=True)
def test_model_declarations_match_installed_schema():
    """Model and state edits alone cannot silently omit database protections."""
    for model in apps.get_models():
        if model._meta.app_label.startswith("stewardship_") and model._meta.managed:
            assert_model_contract(connection, model)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("drift", ["field", "constraint", "index"])
def test_model_contract_detects_declaration_only_changes(monkeypatch, drift):
    """Changing Python declarations alone cannot bless unchanged baseline SQL."""
    model = CampaignConfiguration
    if drift == "field":
        monkeypatch.setattr(model._meta.get_field("name"), "max_length", 253)
    elif drift == "constraint":
        original = next(
            item
            for item in model._meta.constraints
            if item.name == "campaign_ordered_dates"
        )
        replacement = models.CheckConstraint(
            condition=models.Q(end_date__gte=models.F("start_date")),
            name=original.name,
        )
        monkeypatch.setattr(model._meta, "constraints", [replacement])
    else:
        monkeypatch.setattr(
            model._meta,
            "indexes",
            [models.Index(fields=["name"], name="absent_current_model_index")],
        )
    with pytest.raises(AssertionError):
        assert_model_contract(connection, model)
