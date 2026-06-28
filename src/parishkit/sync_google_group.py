"""Implementation for the parishkit-sync-google-group command."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

from parishkit.cli import (
    parser_with_common_options,
    resolve_common_options,
    run_user_facing,
)
from parishkit.config import ConfigData, ConfigError, load_yaml_config
from parishkit.email.base import Email, EmailProvider, provider_from_config
from parishkit.google.auth import (
    load_service_account_credentials,
    load_user_credentials,
)
from parishkit.google.groups import (
    build_admin_directory_service,
    build_groups_settings_service,
    delete_group_member,
    get_group_posting_permissions,
    insert_group_member,
    list_group_members,
    update_group_member_role,
)
from parishkit.logging import setup_logging
from parishkit.parishsoft import ParishSoftData, load_families_and_members
from parishkit.parishsoft_runtime import parishsoft_client_from_config

ADMIN_SCOPE = "https://www.googleapis.com/auth/admin.directory.group.member"
GROUP_SETTINGS_SCOPE = "https://www.googleapis.com/auth/apps.groups.settings"
LEADER_ROLES = {"Chairperson", "Staff"}


@dataclass(frozen=True)
class StaticMember:
    email: str
    leader: bool = False


@dataclass(frozen=True)
class Selector:
    type: str
    ministry_prefix: str | None = None
    member_roles: tuple[str, ...] = ()
    leader_roles: tuple[str, ...] = ()
    staff_owner_domains: tuple[str, ...] = ()
    purpose: str | None = None


@dataclass(frozen=True)
class GroupSync:
    group: str
    notify: tuple[str, ...]
    ministries: tuple[str, ...] = ()
    workgroups: tuple[str, ...] = ()
    static_members: tuple[StaticMember, ...] = ()
    selectors: tuple[Selector, ...] = ()


@dataclass(frozen=True)
class SyncConfig:
    groups: tuple[GroupSync, ...]
    sender: str | None
    google_mail_domains: frozenset[str]


@dataclass
class DesiredMember:
    email: str
    leader: bool
    names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SyncAction:
    action: str
    email: str
    role: str | None = None
    group_member_id: str | None = None
    desired: DesiredMember | None = None


Loader = Callable[..., ParishSoftData]
ServiceFactory = Callable[[ConfigData], tuple[Any, Any]]


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: Loader = load_families_and_members,
    service_factory: ServiceFactory | None = None,
    email_provider: EmailProvider | None = None,
) -> int:
    parser = parser_with_common_options(
        "parishkit-sync-google-group",
        description="Synchronize Google Groups from ParishSoft sources.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show that the console entry point is installed",
    )
    args = parser.parse_args(argv)
    if args.version:
        print(f"parishkit-sync-google-group {version('parishkit')}")
        return 0
    return run_user_facing(lambda: _run(args, loader, service_factory, email_provider))


def _run(
    args: argparse.Namespace,
    loader: Loader,
    service_factory: ServiceFactory | None,
    email_provider: EmailProvider | None,
) -> int:
    common = resolve_common_options(args)
    config = load_yaml_config(common.config)
    sync_config = sync_config_from_yaml(config)
    log = setup_logging(
        verbose=common.verbose or common.dry_run,
        debug=common.debug,
        log_file=common.log_file,
        log_dir=common.log_dir,
        logger_name="parishkit.sync_google_group",
        slack_token_file=common.slack_token_file,
        slack_channel=common.slack_channel,
        slack_level=common.slack_log_level,
    )
    log.info("Configured %s Google Group sync(s)", len(sync_config.groups))
    log.debug("Google Group sync configuration: %s", sync_config.groups)
    client = parishsoft_client_from_config(common, config)
    log.info("Loading active ParishSoft families and members")
    data = loader(client, active_only=True, parishioners_only=False)
    log.info(
        "Loaded %s member(s), %s family/families, %s ministry membership(s), "
        "and %s workgroup membership(s)",
        len(data.members),
        len(data.families),
        len(data.ministry_type_memberships),
        len(data.member_workgroup_memberships),
    )
    log.debug("Dry-run mode is %s", "enabled" if common.dry_run else "disabled")
    admin_service, settings_service = (
        service_factory(config)
        if service_factory is not None
        else build_google_services(load_google_credentials(config))
    )
    provider = email_provider
    if (
        provider is None
        and not common.dry_run
        and any(group.notify for group in sync_config.groups)
    ):
        provider = provider_from_config(_mapping(config.get("email", {}), "email"))
    for group in sync_config.groups:
        log.info("Synchronizing Google Group %s", group.group)
        log.debug(
            "Sources for %s: ministries=%s workgroups=%s static_members=%s "
            "selectors=%s",
            group.group,
            group.ministries,
            group.workgroups,
            group.static_members,
            group.selectors,
        )
        sync_group(
            admin_service,
            settings_service,
            provider,
            data,
            sync_config,
            group,
            dry_run=common.dry_run,
            log=log,
        )
    return 0


def sync_config_from_yaml(config: ConfigData) -> SyncConfig:
    section = _mapping(config.get("sync_google_group", {}), "sync_google_group")
    groups = tuple(
        _group_sync(item, f"sync_google_group.groups[{index}]")
        for index, item in enumerate(
            _list(section.get("groups"), "sync_google_group.groups")
        )
    )
    if not groups:
        raise ConfigError("sync_google_group.groups must not be empty")
    notifications = _mapping(
        section.get("notifications", {}), "sync_google_group.notifications"
    )
    sender = _optional_string(
        notifications.get("sender"), "sync_google_group.notifications.sender"
    )
    domains = _string_list(
        section.get("google_mail_domains", ["gmail.com"]),
        "sync_google_group.google_mail_domains",
    )
    return SyncConfig(
        groups=groups,
        sender=sender,
        google_mail_domains=frozenset(domain.casefold() for domain in domains),
    )


def load_google_credentials(config: ConfigData) -> Any:
    google = _mapping(config.get("google", {}), "google")
    service_account_file = google.get("service_account_file")
    user_token_file = google.get("user_token_file")
    delegated_subject = google.get("delegated_subject")
    scopes = [ADMIN_SCOPE, GROUP_SETTINGS_SCOPE]
    if service_account_file and user_token_file:
        raise ConfigError(
            "google configuration must not set both service_account_file "
            "and user_token_file"
        )
    if delegated_subject is not None and not isinstance(delegated_subject, str):
        raise ConfigError("google.delegated_subject must be a string")
    if isinstance(service_account_file, str):
        return load_service_account_credentials(
            Path(service_account_file),
            scopes=scopes,
            subject=delegated_subject,
        )
    if isinstance(user_token_file, str):
        return load_user_credentials(Path(user_token_file), scopes=scopes)
    raise ConfigError(
        "google.service_account_file or google.user_token_file is required"
    )


def build_google_services(credentials: Any) -> tuple[Any, Any]:
    return (
        build_admin_directory_service(credentials),
        build_groups_settings_service(credentials),
    )


def sync_group(
    admin_service: Any,
    settings_service: Any,
    email_provider: EmailProvider | None,
    data: ParishSoftData,
    config: SyncConfig,
    group: GroupSync,
    *,
    dry_run: bool,
    log: logging.Logger,
) -> list[SyncAction]:
    desired = desired_members(data, group)
    log.info("Computed %s desired member(s) for %s", len(desired), group.group)
    log.debug("Desired members for %s: %s", group.group, desired)
    current = normalized_group_members(list_group_members(admin_service, group.group))
    log.info("Loaded %s current member(s) for %s", len(current), group.group)
    log.debug("Current members for %s: %s", group.group, current)
    actions = compute_actions(desired, current, config.google_mail_domains)
    log.info("Actions for %s: %s", group.group, actions)
    if dry_run:
        log.info(
            "dry-run: would apply %s Google Group action(s) for %s",
            len(actions),
            group.group,
        )
        return actions
    apply_actions(admin_service, group.group, actions)
    log.info("Applied %s Google Group action(s) for %s", len(actions), group.group)
    send_notification(
        email_provider,
        config,
        group,
        get_group_posting_permissions(settings_service, group.group),
        actions,
    )
    return actions


def desired_members(data: ParishSoftData, group: GroupSync) -> list[DesiredMember]:
    found: dict[str, DesiredMember] = {}
    for member in data.members.values():
        is_member, is_leader = member_matches_group(member, group)
        if not is_member and not is_leader:
            continue
        emails = member.get("py emailAddresses") or []
        if not emails:
            continue
        add_desired_member(
            found,
            str(emails[0]).lower(),
            is_leader,
            member.get("py friendly name FL") or member_display_name(member),
        )
    for static_member in group.static_members:
        add_desired_member(found, static_member.email, static_member.leader, None)
    return list(found.values())


def member_matches_group(
    member: Mapping[str, Any],
    group: GroupSync,
) -> tuple[bool, bool]:
    is_member = False
    is_leader = False
    ministry_member, ministry_leader = member_in_ministries(member, group.ministries)
    workgroup_member, workgroup_leader = member_in_workgroups(member, group.workgroups)
    is_member = ministry_member or workgroup_member
    is_leader = ministry_leader or workgroup_leader
    for selector in group.selectors:
        selector_member, selector_leader = selector_matches_member(member, selector)
        is_member = is_member or selector_member
        is_leader = is_leader or selector_leader
    if is_leader:
        is_member = True
    return is_member, is_leader


def compute_actions(
    desired: Sequence[DesiredMember],
    group_members: Sequence[dict[str, Any]],
    google_mail_domains: frozenset[str],
) -> list[SyncAction]:
    actions: list[SyncAction] = []
    matched_group_indexes: set[int] = set()
    for desired_member in desired:
        match_index = next(
            (
                index
                for index, group_member in enumerate(group_members)
                if compare_email(
                    desired_member.email,
                    str(group_member["email"]),
                    google_mail_domains,
                )
            ),
            None,
        )
        desired_role = "OWNER" if desired_member.leader else "MEMBER"
        if match_index is None:
            actions.append(
                SyncAction(
                    action="add",
                    email=desired_member.email,
                    role=desired_role,
                    desired=desired_member,
                )
            )
            continue
        matched_group_indexes.add(match_index)
        group_member = group_members[match_index]
        current_role = str(group_member.get("role", "")).upper()
        if current_role != desired_role:
            actions.append(
                SyncAction(
                    action="change_role",
                    email=desired_member.email,
                    role=desired_role,
                    desired=desired_member,
                )
            )
    for index, group_member in enumerate(group_members):
        if index not in matched_group_indexes:
            actions.append(
                SyncAction(
                    action="delete",
                    email=str(group_member["email"]),
                    group_member_id=str(
                        group_member.get("id") or group_member["email"]
                    ),
                )
            )
    return actions


def apply_actions(service: Any, group_key: str, actions: Sequence[SyncAction]) -> None:
    for action in actions:
        if action.action == "add":
            insert_group_member(
                service, group_key, action.email, action.role or "MEMBER"
            )
        elif action.action == "change_role":
            update_group_member_role(
                service, group_key, action.email, action.role or "MEMBER"
            )
        elif action.action == "delete":
            delete_group_member(
                service, group_key, action.group_member_id or action.email
            )
        else:
            raise ConfigError(f"unknown sync action: {action.action}")


def send_notification(
    provider: EmailProvider | None,
    config: SyncConfig,
    group: GroupSync,
    posting_permission: str | None,
    actions: Sequence[SyncAction],
) -> None:
    if not provider or not group.notify or not actions:
        return
    if not config.sender:
        raise ConfigError("sync_google_group.notifications.sender is required")
    subject = f"Update to Google Group for {group.group}"
    permission_text = posting_permission or "unknown posting policy"
    lines = [
        f"Changes were made to {group.group} ({permission_text}):",
        "",
    ]
    for action in actions:
        names = ", ".join(action.desired.names) if action.desired else ""
        lines.append(f"- {action.action}: {action.email} {action.role or ''} {names}")
    provider.send(
        Email(
            subject=subject,
            sender=config.sender,
            to=group.notify,
            text="\n".join(lines),
        ),
        dry_run=False,
    )


def add_desired_member(
    found: dict[str, DesiredMember],
    email: str,
    leader: bool,
    name: str | None,
) -> None:
    normalized = email.lower()
    existing = found.get(normalized)
    if existing:
        existing.leader = existing.leader or leader
        if name:
            existing.names.append(name)
    else:
        found[normalized] = DesiredMember(
            email=normalized,
            leader=leader,
            names=[name] if name else [],
        )


def member_in_ministries(
    member: Mapping[str, Any],
    ministries: Sequence[str],
) -> tuple[bool, bool]:
    found = False
    leader = False
    configured = set(ministries)
    for ministry in member.get("py ministries", {}).values():
        if ministry.get("name") in configured:
            found = True
            leader = leader or is_ministry_leader(ministry)
    return found, leader


def member_in_workgroups(
    member: Mapping[str, Any],
    workgroups: Sequence[str],
) -> tuple[bool, bool]:
    found = False
    leader = False
    member_workgroups = member.get("py workgroups", {})
    for workgroup in workgroups:
        if workgroup in member_workgroups:
            found = True
        if (
            f"{workgroup} Ldr" in member_workgroups
            or f"{workgroup} Leader" in member_workgroups
        ):
            found = True
            leader = True
    return found, leader


def selector_matches_member(
    member: Mapping[str, Any],
    selector: Selector,
) -> tuple[bool, bool]:
    if selector.type == "ministry_chairs":
        for ministry in member.get("py ministries", {}).values():
            if is_ministry_leader(ministry):
                email = str(member.get("emailAddress") or "")
                domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
                return True, domain in selector.staff_owner_domains
        return False, False
    if selector.type == "ministry_chair":
        for ministry in member.get("py ministries", {}).values():
            if is_ministry_leader(ministry) and str(
                ministry.get("name", "")
            ).startswith(selector.ministry_prefix or ""):
                return True, True
        return False, False
    if selector.type == "ministry_role":
        is_member = False
        is_leader = False
        member_roles = set(selector.member_roles)
        leader_roles = set(selector.leader_roles)
        for ministry in member.get("py ministries", {}).values():
            if not str(ministry.get("name", "")).startswith(
                selector.ministry_prefix or ""
            ):
                continue
            role = ministry.get("role")
            if role in member_roles or role in leader_roles:
                is_member = True
                is_leader = role in leader_roles or is_ministry_leader(ministry)
        return is_member, is_leader
    raise ConfigError(f"unknown sync selector type: {selector.type}")


def is_ministry_leader(ministry: Mapping[str, Any]) -> bool:
    return ministry.get("role") in LEADER_ROLES


def normalize_email(email: str, google_mail_domains: frozenset[str]) -> str:
    if "@" not in email:
        return email.lower()
    local, domain = email.lower().split("@", 1)
    if domain not in google_mail_domains:
        return f"{local}@{domain}"
    local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


def compare_email(left: str, right: str, google_mail_domains: frozenset[str]) -> bool:
    return normalize_email(left, google_mail_domains) == normalize_email(
        right,
        google_mail_domains,
    )


def normalized_group_members(
    members: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "email": str(member["email"]).lower(),
            "role": str(member.get("role", "MEMBER")).upper(),
            "id": str(member.get("id") or member["email"]),
        }
        for member in members
    ]


def member_display_name(member: Mapping[str, Any]) -> str:
    return f"{member.get('firstName', '')} {member.get('lastName', '')}".strip()


def _group_sync(value: Any, name: str) -> GroupSync:
    item = _mapping(value, name)
    group = _required_string(item.get("group", item.get("ggroup")), f"{name}.group")
    notify = tuple(_string_list(item.get("notify", []), f"{name}.notify"))
    ministries = tuple(_string_list(item.get("ministries", []), f"{name}.ministries"))
    workgroups = tuple(_string_list(item.get("workgroups", []), f"{name}.workgroups"))
    static_members = tuple(
        _static_member(static, f"{name}.static_members[{index}]")
        for index, static in enumerate(
            _list(item.get("static_members", []), f"{name}.static_members")
        )
    )
    selectors = tuple(
        _selector(selector, f"{name}.selectors[{index}]")
        for index, selector in enumerate(
            _list(item.get("selectors", []), f"{name}.selectors")
        )
    )
    if not any((ministries, workgroups, static_members, selectors)):
        raise ConfigError(f"{name} must configure a source")
    return GroupSync(
        group=group,
        notify=notify,
        ministries=ministries,
        workgroups=workgroups,
        static_members=static_members,
        selectors=selectors,
    )


def _static_member(value: Any, name: str) -> StaticMember:
    item = _mapping(value, name)
    return StaticMember(
        email=_required_string(item.get("email"), f"{name}.email").lower(),
        leader=_bool(item.get("leader", item.get("owner", False)), f"{name}.leader"),
    )


def _selector(value: Any, name: str) -> Selector:
    item = _mapping(value, name)
    selector_type = _required_string(item.get("type"), f"{name}.type")
    return Selector(
        type=selector_type,
        ministry_prefix=_optional_string(
            item.get("ministry_prefix"), f"{name}.ministry_prefix"
        ),
        member_roles=tuple(
            _string_list(item.get("member_roles", []), f"{name}.member_roles")
        ),
        leader_roles=tuple(
            _string_list(item.get("leader_roles", []), f"{name}.leader_roles")
        ),
        staff_owner_domains=tuple(
            domain.lower()
            for domain in _string_list(
                item.get("staff_owner_domains", []), f"{name}.staff_owner_domains"
            )
        ),
        purpose=_optional_string(item.get("purpose"), f"{name}.purpose"),
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
