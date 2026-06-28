from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from parishkit.config import ConfigError
from parishkit.parishsoft import ParishSoftData
from parishkit.sync_ps_to_cc import (
    cc_sync_config_from_yaml,
    compute_all_actions,
    detect_name_mismatches,
    filter_unsubscribed,
    parishsoft_members_by_email,
    resolve_desired_state,
)
from parishkit.sync_ps_to_cc import (
    main as sync_ps_to_cc_main,
)


class CCClient:
    def __init__(self):
        self.calls = []

    def get_all(self, endpoint, field, **kwargs):
        self.calls.append(("get_all", endpoint, field, kwargs))
        if endpoint == "contact_lists":
            return cc_lists()
        return cc_contacts()

    def post(self, endpoint, body):
        self.calls.append(("post", endpoint, body))
        return {}

    def put(self, endpoint, body):
        self.calls.append(("put", endpoint, body))
        return {}


class EmailProvider:
    def __init__(self):
        self.sent = []

    def send(self, message, *, dry_run=False):
        self.sent.append((message, dry_run))
        return message


def write_config(
    tmp_path: Path, *, dry_run: bool = False, no_sync: bool = False
) -> Path:
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
constant_contact:
  client_id_file: {tmp_path / "constant-contact-client.json"}
  access_token_file: {tmp_path / "constant-contact-token.json"}
email:
  provider: google-workspace
  service_account_file: {tmp_path / "google-service-account.json"}
  delegated_user: no-reply@example.org
sync_ps_to_cc:
  update_names: true
  no_sync: {str(no_sync).lower()}
  notifications:
    sender: no-reply@example.org
  lists:
    - source_workgroup: Newsletter WG
      target_list: Newsletter
      notifications:
        - admin@example.org
""",
        encoding="utf-8",
    )
    return config


def parishsoft_data() -> ParishSoftData:
    members = {
        1: {
            "memberDUID": 1,
            "firstName": "Ann",
            "lastName": "Smith",
            "py friendly name FL": "Ann Smith",
            "emailAddress": "ann@example.org",
            "py emailAddresses": ["ann@example.org"],
        },
        2: {
            "memberDUID": 2,
            "firstName": "Bob",
            "lastName": "Jones",
            "py friendly name FL": "Bob Jones",
            "emailAddress": "bob@example.org",
            "py emailAddresses": ["bob@example.org"],
        },
    }
    return ParishSoftData(
        organization_id=7,
        families={},
        members=members,
        family_groups={},
        family_workgroups={},
        family_workgroup_memberships={},
        member_contactinfos={},
        member_workgroups={},
        member_workgroup_memberships={
            10: {
                "name": "Newsletter WG",
                "membership": [
                    {"py member duid": 1},
                    {"py member duid": 2},
                ],
            }
        },
        ministry_types={},
        ministry_type_memberships={},
        funds={},
        pledges={},
        contributions={},
    )


def cc_lists():
    return [
        {
            "list_id": "list-1",
            "name": "Newsletter",
            "CONTACTS": {"old@example.org": {}},
        }
    ]


def cc_contacts():
    return [
        {
            "contact_id": "contact-ann",
            "email_address": {
                "address": "ann@example.org",
                "permission_to_send": "implicit",
            },
            "first_name": "Anne",
            "last_name": "Smith",
            "list_memberships": [],
        },
        {
            "contact_id": "contact-bob",
            "email_address": {
                "address": "bob@example.org",
                "permission_to_send": "unsubscribed",
            },
            "first_name": "Bob",
            "last_name": "Jones",
            "list_memberships": ["list-1"],
        },
        {
            "contact_id": "contact-old",
            "email_address": {
                "address": "old@example.org",
                "permission_to_send": "implicit",
            },
            "first_name": "Old",
            "last_name": "Member",
            "list_memberships": ["list-1"],
        },
    ]


def test_cc_sync_config_validation():
    config = cc_sync_config_from_yaml(
        {
            "sync_ps_to_cc": {
                "update_names": True,
                "notifications": {"sender": "no-reply@example.org"},
                "lists": [
                    {
                        "source_workgroup": "Newsletter WG",
                        "target_list": "Newsletter",
                        "notifications": ["admin@example.org"],
                    }
                ],
            }
        }
    )

    assert config.update_names
    assert config.mappings[0].source_workgroup == "Newsletter WG"


def test_cc_sync_config_rejects_missing_lists():
    with pytest.raises(ConfigError, match="lists"):
        cc_sync_config_from_yaml({"sync_ps_to_cc": {}})


def test_desired_state_and_unsubscribed_filtering():
    config = cc_sync_config_from_yaml(
        {
            "sync_ps_to_cc": {
                "lists": [
                    {
                        "source_workgroup": "Newsletter WG",
                        "target_list": "Newsletter",
                    }
                ]
            }
        }
    )
    data = parishsoft_data()
    desired = resolve_desired_state(config, data, cc_lists())

    assert desired == [{"ann@example.org", "bob@example.org"}]

    unsubscribed = filter_unsubscribed(
        cc_contacts(),
        desired,
        parishsoft_members_by_email(data.members),
    )

    assert desired == [{"ann@example.org"}]
    assert unsubscribed[0][0][0] == "bob@example.org"
    assert "Bob Jones" in unsubscribed[0][0][1]


def test_action_computation_and_name_updates():
    config = cc_sync_config_from_yaml(
        {
            "sync_ps_to_cc": {
                "update_names": True,
                "lists": [
                    {
                        "source_workgroup": "Newsletter WG",
                        "target_list": "Newsletter",
                    }
                ],
            }
        }
    )
    desired = [{"ann@example.org", "new@example.org"}]
    contacts = {item["email_address"]["address"]: item for item in cc_contacts()}
    contacts["ann@example.org"]["PS MEMBERS"] = [parishsoft_data().members[1]]

    actions = compute_all_actions(config, desired, cc_lists(), contacts)
    actions.extend(detect_name_mismatches(contacts, update_names=True))

    assert [(item.type, item.email, item.list_uuid) for item in actions] == [
        ("create", "new@example.org", None),
        ("subscribe", "ann@example.org", "list-1"),
        ("subscribe", "new@example.org", "list-1"),
        ("unsubscribe", "old@example.org", "list-1"),
        ("update_name", "ann@example.org", None),
    ]


def test_sync_ps_to_cc_main_writes_constant_contact_and_email(tmp_path, monkeypatch):
    cc = CCClient()
    email = EmailProvider()
    loader_calls = []
    monkeypatch.setattr(
        "parishkit.sync_ps_to_cc.parishsoft_client_from_config",
        lambda _common, _config: SimpleNamespace(),
    )

    def loader(_client, **kwargs):
        loader_calls.append(kwargs)
        return parishsoft_data()

    assert (
        sync_ps_to_cc_main(
            ["--config", str(write_config(tmp_path))],
            loader=loader,
            cc_factory=lambda _config: cc,
            email_provider=email,
        )
        == 0
    )

    assert loader_calls == [{"active_only": True, "parishioners_only": False}]
    assert any(call[0] == "post" for call in cc.calls)
    assert any(call[0] == "put" for call in cc.calls)
    assert email.sent
    assert email.sent[0][0].to == ("admin@example.org",)


def test_sync_ps_to_cc_dry_run_and_no_sync_skip_writes(tmp_path, monkeypatch):
    cc = CCClient()
    config = write_config(tmp_path, dry_run=True, no_sync=True)
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace("email:\n", "unused_email:\n"), encoding="utf-8")
    monkeypatch.setattr(
        "parishkit.sync_ps_to_cc.parishsoft_client_from_config",
        lambda _common, _config: SimpleNamespace(),
    )

    assert (
        sync_ps_to_cc_main(
            ["--config", str(config)],
            loader=lambda _client, **_kwargs: parishsoft_data(),
            cc_factory=lambda _config: cc,
        )
        == 0
    )

    assert [call[0] for call in cc.calls] == ["get_all", "get_all"]
