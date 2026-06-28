from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import pytest

from parishkit.config import ConfigError
from parishkit.create_ministry_rosters import (
    RosterMember,
    ministry_roster_members,
    roster_config_from_yaml,
    roster_role_matches,
    roster_values,
    workgroup_roster_members,
)
from parishkit.create_ministry_rosters import (
    main as create_ministry_rosters_main,
)
from parishkit.parishsoft import ParishSoftData


class Request:
    def execute(self):
        return {}


class Values:
    def __init__(self):
        self.calls = []

    def clear(self, **kwargs):
        self.calls.append(("clear", kwargs))
        return Request()

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        return Request()


class Spreadsheets:
    def __init__(self):
        self._values = Values()

    def values(self):
        return self._values


class SheetsService:
    def __init__(self):
        self._spreadsheets = Spreadsheets()

    def spreadsheets(self):
        return self._spreadsheets


def write_config(tmp_path: Path, *, dry_run: bool = False) -> Path:
    api_key = tmp_path / "parishsoft-api-key.txt"
    api_key.write_text("key", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
common:
  dry_run: {str(dry_run).lower()}
parishsoft:
  api_key_file: {api_key}
  cache_dir: {tmp_path / "cache"}
  cache_limit: 1d
google:
  user_token_file: {tmp_path / "google-user-token.json"}
create_ministry_rosters:
  spreadsheet_id: default-sheet
  ministries:
    - ministry: Readers
      range: Readers!A1
      clear_range: Readers!A:Z
      include_birthday: true
      role_sheets:
        - name: Reader Leads
          roles:
            - Lead
          spreadsheet_id: lead-sheet
          range: Leads!A1
          clear_range: Leads!A:Z
  workgroups:
    - workgroup: Movers
      spreadsheet_id: movers-sheet
      range: Movers!A1
      clear_range: Movers!A:Z
""",
        encoding="utf-8",
    )
    return config


def parishsoft_data() -> ParishSoftData:
    family = {
        "familyDUID": 10,
        "primaryAddress1": "1 Main St",
        "primaryCity": "Louisville",
        "primaryState": "KY",
        "primaryPostalCode": "40202",
    }
    members = {
        1: {
            "memberDUID": 1,
            "familyDUID": 10,
            "firstName": "Ann",
            "lastName": "Smith",
            "py friendly name LF": "Smith, Ann",
            "py family": family,
            "family_PublishPhone": True,
            "family_PublishEMail": True,
            "mobilePhone": "502-555-1000",
            "py emailAddresses": ["ann@example.org"],
            "birthdate": dt.date(1980, 5, 4),
            "py ministries": {"Readers": {"role": "Lead"}},
            "py workgroups": {"Movers": {"name": "Movers"}},
        },
        2: {
            "memberDUID": 2,
            "familyDUID": 10,
            "firstName": "Bob",
            "lastName": "Adams",
            "py friendly name LF": "Adams, Bob",
            "py family": family,
            "family_PublishPhone": False,
            "family_PublishEMail": False,
            "py ministries": {"Readers": {"role": "Member"}},
            "py workgroups": {"Movers Ldr": {"name": "Movers Ldr"}},
        },
    }
    return ParishSoftData(
        organization_id=7,
        families={10: family},
        members=members,
        family_groups={},
        family_workgroups={},
        family_workgroup_memberships={},
        member_contactinfos={},
        member_workgroups={},
        member_workgroup_memberships={},
        ministry_types={},
        ministry_type_memberships={},
        funds={},
        pledges={},
        contributions={},
    )


def test_roster_config_validation_and_role_sheets():
    config = roster_config_from_yaml(
        {
            "create_ministry_rosters": {
                "spreadsheet_id": "default-sheet",
                "ministries": [
                    {
                        "ministries": ["Readers", "Greeters"],
                        "name": "Welcome Ministers",
                        "include_birthday": True,
                        "role sheets": [
                            {
                                "name": "Leads",
                                "roles": ["Lead"],
                                "spreadsheet_id": "lead-sheet",
                            }
                        ],
                    }
                ],
            }
        }
    )

    assert config.ministries[0].name == "Welcome Ministers"
    assert config.ministries[0].source_names == ("Readers", "Greeters")
    assert config.ministries[0].role_sheets[0].spreadsheet_id == "lead-sheet"


def test_roster_config_rejects_missing_targets():
    with pytest.raises(ConfigError, match="ministries or workgroups"):
        roster_config_from_yaml({"create_ministry_rosters": {"ministries": []}})


def test_roster_generation_for_ministries_and_workgroups():
    data = parishsoft_data()

    ministry_members = ministry_roster_members(data, ["Readers"])
    workgroup_members = workgroup_roster_members(
        data,
        "Movers",
        leader_suffix=" Ldr",
    )

    assert [(item.member["memberDUID"], item.role) for item in ministry_members] == [
        (2, "Member"),
        (1, "Lead"),
    ]
    assert [(item.member["memberDUID"], item.role) for item in workgroup_members] == [
        (2, "Leader"),
        (1, "Member"),
    ]
    assert roster_role_matches("Lead, Member", {"Lead"})


def test_roster_values_include_contacts_and_birthday():
    member = parishsoft_data().members[1]

    values = roster_values(
        "Readers",
        [RosterMember(member=member, role="Lead")],
        include_birthday=True,
        now=dt.datetime(2026, 1, 2, 3, 4),
    )

    assert values[:4] == [
        ["Ministry: Readers"],
        ["Last updated: 2026-01-02 03:04:00"],
        [],
        ["Member name", "Address", "Phone / email", "Birthday", "Role"],
    ]
    assert values[4] == [
        "Smith, Ann",
        "1 Main St\nLouisville, KY 40202",
        "502-555-1000 cell\nann@example.org",
        "May 4",
        "Lead",
    ]


def test_create_ministry_rosters_main_writes_sheet_values(tmp_path, monkeypatch):
    service = SheetsService()
    loader_calls = []
    monkeypatch.setattr(
        "parishkit.create_ministry_rosters.parishsoft_client_from_config",
        lambda _common, _config: SimpleNamespace(),
    )

    def loader(_client, **kwargs):
        loader_calls.append(kwargs)
        return parishsoft_data()

    assert (
        create_ministry_rosters_main(
            ["--config", str(write_config(tmp_path))],
            loader=loader,
            sheets_factory=lambda _config: service,
        )
        == 0
    )

    assert loader_calls == [{"active_only": True, "parishioners_only": False}]
    calls = service._spreadsheets._values.calls
    assert calls[0] == (
        "clear",
        {
            "spreadsheetId": "default-sheet",
            "range": "Readers!A:Z",
            "body": {},
        },
    )
    assert calls[1][0] == "update"
    assert calls[1][1]["spreadsheetId"] == "default-sheet"
    assert calls[1][1]["range"] == "Readers!A1"
    assert calls[1][1]["body"]["values"][4][-1] == "Member"
    assert calls[2][1]["spreadsheetId"] == "lead-sheet"
    assert calls[3][1]["body"]["values"][4][0] == "Smith, Ann"
    assert calls[4][1]["spreadsheetId"] == "movers-sheet"


def test_create_ministry_rosters_dry_run_skips_sheet_writes(tmp_path, monkeypatch):
    service = SheetsService()
    monkeypatch.setattr(
        "parishkit.create_ministry_rosters.parishsoft_client_from_config",
        lambda _common, _config: SimpleNamespace(),
    )

    assert (
        create_ministry_rosters_main(
            ["--config", str(write_config(tmp_path, dry_run=True))],
            loader=lambda _client, **_kwargs: parishsoft_data(),
            sheets_factory=lambda _config: service,
        )
        == 0
    )

    assert service._spreadsheets._values.calls == []
