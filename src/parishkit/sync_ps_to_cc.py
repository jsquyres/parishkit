"""Implementation for the parishkit-sync-ps-to-cc command."""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from parishkit.cli import (
    parser_with_common_options,
    resolve_common_options,
    run_user_facing,
)
from parishkit.config import ConfigData, ConfigError, load_yaml_config
from parishkit.constant_contact import (
    ConstantContactClient,
    ConstantContactConfig,
    create_contact_dict,
    get_access_token,
    link_cc_data,
    link_contacts_to_ps_members,
    load_client_id,
    sign_up_form_body,
    update_contact_body,
)
from parishkit.email.base import Email, EmailProvider, provider_from_config
from parishkit.logging import setup_logging
from parishkit.parishsoft import ParishSoftData, load_families_and_members
from parishkit.parishsoft_runtime import parishsoft_client_from_config


@dataclass(frozen=True)
class CCSyncMapping:
    source_workgroup: str
    target_list: str
    notifications: tuple[str, ...] = ()


@dataclass(frozen=True)
class CCSyncConfig:
    mappings: tuple[CCSyncMapping, ...]
    update_names: bool = False
    no_sync: bool = False
    sender: str | None = None


@dataclass(frozen=True)
class CCAction:
    type: str
    email: str
    sync_index: int | None
    detail: str
    list_name: str | None = None
    list_uuid: str | None = None
    new_first: str | None = None
    new_last: str | None = None


Loader = Callable[..., ParishSoftData]
CCFactory = Callable[[ConfigData], ConstantContactClient]


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: Loader = load_families_and_members,
    cc_factory: CCFactory | None = None,
    email_provider: EmailProvider | None = None,
) -> int:
    parser = parser_with_common_options(
        "parishkit-sync-ps-to-cc",
        description="Synchronize ParishSoft workgroups to Constant Contact lists.",
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--update-names", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print(f"parishkit-sync-ps-to-cc {version('parishkit')}")
        return 0
    return run_user_facing(lambda: _run(args, loader, cc_factory, email_provider))


def _run(
    args: argparse.Namespace,
    loader: Loader,
    cc_factory: CCFactory | None,
    email_provider: EmailProvider | None,
) -> int:
    common = resolve_common_options(args)
    config = load_yaml_config(common.config)
    sync_config = cc_sync_config_from_yaml(config)
    sync_config = CCSyncConfig(
        mappings=sync_config.mappings,
        update_names=sync_config.update_names or bool(args.update_names),
        no_sync=sync_config.no_sync or bool(args.no_sync),
        sender=sync_config.sender,
    )
    log = setup_logging(
        verbose=common.verbose or common.dry_run,
        debug=common.debug,
        log_file=common.log_file,
        log_dir=common.log_dir,
        logger_name="parishkit.sync_ps_to_cc",
        slack_token_file=common.slack_token_file,
        slack_channel=common.slack_channel,
        slack_level=common.slack_log_level,
    )
    log.info(
        "Configured %s Constant Contact list sync(s); update_names=%s no_sync=%s",
        len(sync_config.mappings),
        sync_config.update_names,
        sync_config.no_sync,
    )
    log.debug("Constant Contact sync mappings: %s", sync_config.mappings)
    ps_client = parishsoft_client_from_config(common, config)
    log.info("Loading active ParishSoft families and members")
    data = loader(ps_client, active_only=True, parishioners_only=False)
    log.info(
        "Loaded %s member(s), %s family/families, %s ministry membership(s), "
        "and %s workgroup membership(s)",
        len(data.members),
        len(data.families),
        len(data.ministry_type_memberships),
        len(data.member_workgroup_memberships),
    )
    log.debug("Dry-run mode is %s", "enabled" if common.dry_run else "disabled")
    cc_client = cc_factory(config) if cc_factory else constant_contact_client(config)
    log.info("Loading Constant Contact lists and contacts")
    cc_lists, cc_contacts = load_cc_data(cc_client)
    log.info(
        "Loaded %s Constant Contact list(s) and %s contact(s)",
        len(cc_lists),
        len(cc_contacts),
    )
    ps_members_by_email = parishsoft_members_by_email(data.members)
    link_contacts_to_ps_members(cc_contacts, data.members)
    desired_emails = resolve_desired_state(sync_config, data, cc_lists)
    for mapping, emails in zip(sync_config.mappings, desired_emails, strict=True):
        log.info(
            "Resolved %s desired email(s) from %s to %s",
            len(emails),
            mapping.source_workgroup,
            mapping.target_list,
        )
        log.debug("Desired emails for %s: %s", mapping.target_list, sorted(emails))
    unsubscribed = filter_unsubscribed(
        cc_contacts,
        desired_emails,
        ps_members_by_email,
    )
    filtered_count = sum(len(items) for items in unsubscribed)
    if filtered_count:
        log.info("Filtered %s unsubscribed desired address(es)", filtered_count)
        log.debug("Filtered unsubscribed addresses: %s", unsubscribed)
    contacts_by_email = {
        contact["email_address"]["address"].lower(): contact for contact in cc_contacts
    }
    actions = compute_all_actions(
        sync_config,
        desired_emails,
        cc_lists,
        contacts_by_email,
    )
    actions.extend(
        detect_name_mismatches(
            contacts_by_email,
            update_names=sync_config.update_names,
        )
    )
    execute_actions(
        cc_client,
        actions,
        contacts_by_email,
        ps_members_by_email,
        dry_run=common.dry_run,
        no_sync=sync_config.no_sync,
        log=log,
    )
    provider = email_provider
    if (
        provider is None
        and not common.dry_run
        and not sync_config.no_sync
        and any(mapping.notifications for mapping in sync_config.mappings)
    ):
        provider = provider_from_config(_mapping(config.get("email", {}), "email"))
    send_notifications(provider, sync_config, actions, unsubscribed)
    log.info("Computed %s Constant Contact action(s)", len(actions))
    return 0


def cc_sync_config_from_yaml(config: ConfigData) -> CCSyncConfig:
    section = _mapping(config.get("sync_ps_to_cc", {}), "sync_ps_to_cc")
    mappings = tuple(
        _mapping_config(item, f"sync_ps_to_cc.lists[{index}]")
        for index, item in enumerate(_list(section.get("lists"), "sync_ps_to_cc.lists"))
    )
    if not mappings:
        raise ConfigError("sync_ps_to_cc.lists must not be empty")
    notifications = _mapping(
        section.get("notifications", {}), "sync_ps_to_cc.notifications"
    )
    sender = _optional_string(
        notifications.get("sender"), "sync_ps_to_cc.notifications.sender"
    )
    return CCSyncConfig(
        mappings=mappings,
        update_names=_bool(
            section.get("update_names", False), "sync_ps_to_cc.update_names"
        ),
        no_sync=_bool(section.get("no_sync", False), "sync_ps_to_cc.no_sync"),
        sender=sender,
    )


def constant_contact_client(config: ConfigData) -> ConstantContactClient:
    section = _mapping(config.get("constant_contact", {}), "constant_contact")
    client_id_file = _required_string(
        section.get("client_id_file"), "constant_contact.client_id_file"
    )
    access_token_file = _required_string(
        section.get("access_token_file"), "constant_contact.access_token_file"
    )
    client_id = load_client_id(Path(client_id_file))
    access_token = get_access_token(Path(access_token_file), client_id)
    return ConstantContactClient(
        ConstantContactConfig(client_id=client_id, access_token=access_token)
    )


def load_cc_data(
    client: ConstantContactClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lists = client.get_all("contact_lists", "lists")
    contacts = client.get_all(
        "contacts",
        "contacts",
        include="list_memberships",
        status="all",
    )
    link_cc_data(contacts, [], lists)
    return lists, contacts


def resolve_desired_state(
    config: CCSyncConfig,
    data: ParishSoftData,
    cc_lists: Sequence[Mapping[str, Any]],
) -> list[set[str]]:
    desired = []
    list_by_name = {item["name"]: item for item in cc_lists}
    workgroup_by_name = {
        item["name"]: item for item in data.member_workgroup_memberships.values()
    }
    for mapping in config.mappings:
        workgroup = workgroup_by_name.get(mapping.source_workgroup)
        if workgroup is None:
            raise ConfigError(
                f"ParishSoft workgroup not found: {mapping.source_workgroup}"
            )
        cc_list = list_by_name.get(mapping.target_list)
        if cc_list is None:
            raise ConfigError(f"Constant Contact list not found: {mapping.target_list}")
        emails = set()
        for item in workgroup.get("membership", []):
            member_id = item.get("py member duid")
            member = data.members.get(member_id)
            if member and member.get("py emailAddresses"):
                emails.add(str(member["py emailAddresses"][0]).lower())
        desired.append(emails)
    return desired


def filter_unsubscribed(
    contacts: Sequence[Mapping[str, Any]],
    desired_emails: list[set[str]],
    ps_members_by_email: Mapping[str, list[dict[str, Any]]],
) -> list[list[tuple[str, str, str]]]:
    unsubscribed = [[] for _ in desired_emails]
    for contact in contacts:
        email_address = contact.get("email_address", {})
        if email_address.get("permission_to_send") != "unsubscribed":
            continue
        email = str(email_address.get("address", "")).lower()
        for index, desired in enumerate(desired_emails):
            if email not in desired:
                continue
            desired.discard(email)
            members = ps_members_by_email.get(email, [])
            names = ", ".join(
                str(member.get("py friendly name FL", "")) for member in members
            )
            duids = ", ".join(str(member.get("memberDUID", "")) for member in members)
            unsubscribed[index].append((email, names, duids))
    return unsubscribed


def compute_all_actions(
    config: CCSyncConfig,
    desired_emails: Sequence[set[str]],
    cc_lists: Sequence[Mapping[str, Any]],
    contacts_by_email: Mapping[str, Mapping[str, Any]],
) -> list[CCAction]:
    actions = []
    actions.extend(compute_create_actions(desired_emails, contacts_by_email))
    actions.extend(
        compute_subscribe_unsubscribe_actions(config, desired_emails, cc_lists)
    )
    return actions


def compute_create_actions(
    desired_emails: Sequence[set[str]],
    contacts_by_email: Mapping[str, Mapping[str, Any]],
) -> list[CCAction]:
    actions = []
    all_desired = set().union(*desired_emails) if desired_emails else set()
    for email in sorted(all_desired - set(contacts_by_email)):
        sync_index = next(
            index for index, emails in enumerate(desired_emails) if email in emails
        )
        actions.append(
            CCAction(
                type="create",
                email=email,
                sync_index=sync_index,
                detail=f"Create contact for {email}",
            )
        )
    return actions


def compute_subscribe_unsubscribe_actions(
    config: CCSyncConfig,
    desired_emails: Sequence[set[str]],
    cc_lists: Sequence[Mapping[str, Any]],
) -> list[CCAction]:
    cc_list_by_name = {item["name"]: item for item in cc_lists}
    actions = []
    for index, mapping in enumerate(config.mappings):
        cc_list = cc_list_by_name[mapping.target_list]
        list_uuid = cc_list["list_id"]
        current = set(cc_list.get("CONTACTS", {}))
        for email in sorted(desired_emails[index] - current):
            actions.append(
                CCAction(
                    type="subscribe",
                    email=email,
                    list_name=mapping.target_list,
                    list_uuid=list_uuid,
                    detail=f"Subscribe {email} to {mapping.target_list}",
                    sync_index=index,
                )
            )
        for email in sorted(current - desired_emails[index]):
            actions.append(
                CCAction(
                    type="unsubscribe",
                    email=email,
                    list_name=mapping.target_list,
                    list_uuid=list_uuid,
                    detail=f"Unsubscribe {email} from {mapping.target_list}",
                    sync_index=index,
                )
            )
    return actions


def detect_name_mismatches(
    contacts_by_email: Mapping[str, Mapping[str, Any]],
    *,
    update_names: bool,
) -> list[CCAction]:
    if not update_names:
        return []
    from parishkit.parishsoft import salutation_for_members

    actions = []
    for email, contact in contacts_by_email.items():
        members = contact.get("PS MEMBERS")
        if not members:
            continue
        first, last = salutation_for_members(members)
        first = first.replace(".", "")
        if first == contact.get("first_name", "") and last == contact.get(
            "last_name", ""
        ):
            continue
        actions.append(
            CCAction(
                type="update_name",
                email=email,
                sync_index=None,
                detail=f"Update name for {email}",
                new_first=first,
                new_last=last,
            )
        )
    return actions


def execute_actions(
    client: ConstantContactClient,
    actions: Sequence[CCAction],
    contacts_by_email: Mapping[str, Mapping[str, Any]],
    ps_members_by_email: Mapping[str, list[dict[str, Any]]],
    *,
    dry_run: bool,
    no_sync: bool,
    log: logging.Logger | None = None,
) -> None:
    grouped: dict[str, list[CCAction]] = defaultdict(list)
    for action in actions:
        grouped[action.email].append(action)
    for email, email_actions in grouped.items():
        post_body = post_body_for_actions(
            email, email_actions, contacts_by_email, ps_members_by_email
        )
        put_body = put_body_for_actions(email, email_actions, contacts_by_email)
        if post_body and put_body:
            for list_id in post_body.get("list_memberships", []):
                if list_id not in put_body["list_memberships"]:
                    put_body["list_memberships"].append(list_id)
        if dry_run or no_sync:
            if log:
                mode = "dry-run" if dry_run else "no-sync"
                log.info(
                    "%s: would apply %s Constant Contact action(s) for %s",
                    mode,
                    len(email_actions),
                    email,
                )
                log.debug("%s: POST body for %s: %s", mode, email, post_body)
                log.debug("%s: PUT body for %s: %s", mode, email, put_body)
            continue
        if post_body:
            if log:
                log.debug(
                    "Posting Constant Contact sign-up body for %s: %s", email, post_body
                )
            client.post("contacts/sign_up_form", sign_up_form_body(post_body))
        if put_body:
            if log:
                log.debug(
                    "Putting Constant Contact update body for %s: %s", email, put_body
                )
            client.put(
                f"contacts/{put_body['contact_id']}", update_contact_body(put_body)
            )


def post_body_for_actions(
    email: str,
    actions: Sequence[CCAction],
    contacts_by_email: Mapping[str, Mapping[str, Any]],
    ps_members_by_email: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    creates = [action for action in actions if action.type == "create"]
    subscribes = [action for action in actions if action.type == "subscribe"]
    if not creates and not subscribes:
        return None
    if creates:
        body = create_contact_dict(email, ps_members_by_email[email])
    else:
        contact = contacts_by_email[email]
        body = {
            "email_address": {"address": email},
            "first_name": contact.get("first_name", ""),
            "last_name": contact.get("last_name", ""),
            "list_memberships": [],
        }
    body["list_memberships"] = [
        action.list_uuid for action in subscribes if action.list_uuid
    ]
    return body


def put_body_for_actions(
    email: str,
    actions: Sequence[CCAction],
    contacts_by_email: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    unsubscribes = [action for action in actions if action.type == "unsubscribe"]
    name_updates = [action for action in actions if action.type == "update_name"]
    if not unsubscribes and not name_updates:
        return None
    contact = contacts_by_email[email]
    body = {
        "contact_id": contact["contact_id"],
        "email_address": contact["email_address"],
        "first_name": contact.get("first_name", ""),
        "last_name": contact.get("last_name", ""),
        "list_memberships": list(contact.get("list_memberships", [])),
    }
    for action in unsubscribes:
        if action.list_uuid in body["list_memberships"]:
            body["list_memberships"].remove(action.list_uuid)
    if name_updates:
        update = name_updates[-1]
        body["first_name"] = update.new_first or body["first_name"]
        body["last_name"] = update.new_last or body["last_name"]
    return body


def send_notifications(
    provider: EmailProvider | None,
    config: CCSyncConfig,
    actions: Sequence[CCAction],
    unsubscribed: Sequence[Sequence[tuple[str, str, str]]],
) -> None:
    if provider is None or not config.sender:
        return
    for index, mapping in enumerate(config.mappings):
        list_actions = [action for action in actions if action.sync_index == index]
        if not list_actions and not unsubscribed[index]:
            continue
        lines = [
            f"Constant Contact sync update: {mapping.target_list}",
            f"ParishSoft workgroup: {mapping.source_workgroup}",
            "",
        ]
        lines.extend(action.detail for action in list_actions)
        for email, names, duids in unsubscribed[index]:
            lines.append(f"Unsubscribed contact filtered: {email} {names} {duids}")
        provider.send(
            Email(
                subject=f"Constant Contact sync update: {mapping.target_list}",
                sender=config.sender,
                to=mapping.notifications,
                text="\n".join(lines),
            ),
            dry_run=False,
        )


def parishsoft_members_by_email(
    members: Mapping[int, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_email: dict[str, list[dict[str, Any]]] = {}
    for member in members.values():
        for email in member.get("py emailAddresses", []):
            by_email.setdefault(str(email).lower(), []).append(member)
    return by_email


def _mapping_config(value: Any, name: str) -> CCSyncMapping:
    item = _mapping(value, name)
    return CCSyncMapping(
        source_workgroup=_required_string(
            item.get("source_workgroup", item.get("source ps member wg")),
            f"{name}.source_workgroup",
        ),
        target_list=_required_string(
            item.get("target_list", item.get("target cc list")),
            f"{name}.target_list",
        ),
        notifications=tuple(
            _string_list(item.get("notifications", []), f"{name}.notifications")
        ),
    )


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"{name} must be a list")
    return value


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be a list of strings")
    return value


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name} must be a string")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    if value in (None, ""):
        return None
    return _required_string(value, name)


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be a boolean")
    return value
