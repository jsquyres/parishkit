"""Implementation for the parishkit-create-ministry-rosters command."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
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
from parishkit.google.auth import (
    load_service_account_credentials,
    load_user_credentials,
)
from parishkit.google.sheets import build_sheets_service, clear_values, update_values
from parishkit.logging import setup_logging
from parishkit.parishsoft import (
    ParishSoftData,
    get_member_public_email,
    get_member_public_phones,
    load_families_and_members,
)
from parishkit.parishsoft_runtime import parishsoft_client_from_config

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_RANGE = "Roster!A1"
DEFAULT_CLEAR_RANGE = "Roster!A:Z"
DEFAULT_LEADER_SUFFIX = " Ldr"


@dataclass(frozen=True)
class RoleRosterTarget:
    name: str
    roles: tuple[str, ...]
    spreadsheet_id: str
    range_name: str
    clear_range: str


@dataclass(frozen=True)
class RosterTarget:
    name: str
    source_type: str
    source_names: tuple[str, ...]
    spreadsheet_id: str
    range_name: str
    clear_range: str
    include_birthday: bool
    role_sheets: tuple[RoleRosterTarget, ...] = ()


@dataclass(frozen=True)
class RosterConfig:
    ministries: tuple[RosterTarget, ...]
    workgroups: tuple[RosterTarget, ...]
    workgroup_leader_suffix: str = DEFAULT_LEADER_SUFFIX


@dataclass(frozen=True)
class RosterMember:
    member: dict[str, Any]
    role: str


Loader = Callable[..., ParishSoftData]
SheetsFactory = Callable[[ConfigData], Any]


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: Loader = load_families_and_members,
    sheets_factory: SheetsFactory | None = None,
) -> int:
    parser = parser_with_common_options(
        "parishkit-create-ministry-rosters",
        description="Write ParishSoft ministry rosters to Google Sheets.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show that the console entry point is installed",
    )
    args = parser.parse_args(argv)
    if args.version:
        print(f"parishkit-create-ministry-rosters {version('parishkit')}")
        return 0
    return run_user_facing(lambda: _run(args, loader, sheets_factory))


def _run(
    args: argparse.Namespace,
    loader: Loader,
    sheets_factory: SheetsFactory | None,
) -> int:
    common = resolve_common_options(args)
    config = load_yaml_config(common.config)
    roster_config = roster_config_from_yaml(config)
    log = setup_logging(
        verbose=common.verbose,
        debug=common.debug,
        log_file=common.log_file,
        log_dir=common.log_dir,
        logger_name="parishkit.create_ministry_rosters",
        slack_token_file=common.slack_token_file,
        slack_channel=common.slack_channel,
        slack_level=common.slack_log_level,
    )
    log.info(
        "Configured %s ministry roster(s) and %s workgroup roster(s)",
        len(roster_config.ministries),
        len(roster_config.workgroups),
    )
    log.debug("Ministry roster targets: %s", roster_config.ministries)
    log.debug("Workgroup roster targets: %s", roster_config.workgroups)
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
    sheets_service = (
        sheets_factory(config)
        if sheets_factory is not None
        else build_sheets_service(load_sheets_credentials(config))
    )
    write_configured_rosters(
        sheets_service,
        data,
        roster_config,
        dry_run=common.dry_run,
        log=log,
    )
    return 0


def roster_config_from_yaml(config: ConfigData) -> RosterConfig:
    section = _mapping(
        config.get("create_ministry_rosters", {}),
        "create_ministry_rosters",
    )
    default_spreadsheet_id = section.get("spreadsheet_id")
    if default_spreadsheet_id is not None and not isinstance(
        default_spreadsheet_id, str
    ):
        raise ConfigError("create_ministry_rosters.spreadsheet_id must be a string")
    default_range = _optional_string(
        section.get("range"), "create_ministry_rosters.range"
    )
    default_clear_range = _optional_string(
        section.get("clear_range"),
        "create_ministry_rosters.clear_range",
    )
    leader_suffix = section.get("workgroup_leader_suffix", DEFAULT_LEADER_SUFFIX)
    if not isinstance(leader_suffix, str):
        raise ConfigError(
            "create_ministry_rosters.workgroup_leader_suffix must be a string"
        )
    ministries = tuple(
        _target(
            item,
            f"create_ministry_rosters.ministries[{index}]",
            source_key="ministry",
            plural_source_key="ministries",
            source_type="ministry",
            default_spreadsheet_id=default_spreadsheet_id,
            default_range=default_range,
            default_clear_range=default_clear_range,
        )
        for index, item in enumerate(
            _list(section.get("ministries", []), "create_ministry_rosters.ministries")
        )
    )
    workgroups = tuple(
        _target(
            item,
            f"create_ministry_rosters.workgroups[{index}]",
            source_key="workgroup",
            plural_source_key=None,
            source_type="workgroup",
            default_spreadsheet_id=default_spreadsheet_id,
            default_range=default_range,
            default_clear_range=default_clear_range,
        )
        for index, item in enumerate(
            _list(section.get("workgroups", []), "create_ministry_rosters.workgroups")
        )
    )
    if not ministries and not workgroups:
        raise ConfigError(
            "create_ministry_rosters must configure ministries or workgroups"
        )
    return RosterConfig(
        ministries=ministries,
        workgroups=workgroups,
        workgroup_leader_suffix=leader_suffix,
    )


def load_sheets_credentials(config: ConfigData) -> Any:
    google = _mapping(config.get("google", {}), "google")
    service_account_file = google.get("service_account_file")
    user_token_file = google.get("user_token_file")
    delegated_subject = google.get("delegated_subject")
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
            scopes=[SHEETS_SCOPE],
            subject=delegated_subject,
        )
    if isinstance(user_token_file, str):
        return load_user_credentials(Path(user_token_file), scopes=[SHEETS_SCOPE])
    raise ConfigError(
        "google.service_account_file or google.user_token_file is required"
    )


def write_configured_rosters(
    sheets_service: Any,
    data: ParishSoftData,
    config: RosterConfig,
    *,
    dry_run: bool,
    log: logging.Logger,
) -> None:
    for target in config.ministries:
        log.debug(
            "Preparing ministry roster %s from %s", target.name, target.source_names
        )
        members = ministry_roster_members(data, target.source_names)
        write_roster_target(
            sheets_service,
            target,
            members,
            dry_run=dry_run,
            log=log,
        )
        for role_target in target.role_sheets:
            allowed_roles = set(role_target.roles)
            log.debug(
                "Preparing role roster %s from %s role(s): %s",
                role_target.name,
                target.name,
                role_target.roles,
            )
            role_members = [
                member
                for member in members
                if roster_role_matches(member.role, allowed_roles)
            ]
            write_values(
                sheets_service,
                role_target.spreadsheet_id,
                role_target.range_name,
                role_target.clear_range,
                roster_values(
                    role_target.name,
                    role_members,
                    include_birthday=target.include_birthday,
                ),
                dry_run=dry_run,
                log=log,
            )
    for target in config.workgroups:
        log.debug(
            "Preparing workgroup roster %s from %s", target.name, target.source_names
        )
        members = workgroup_roster_members(
            data,
            target.source_names[0],
            leader_suffix=config.workgroup_leader_suffix,
        )
        write_roster_target(
            sheets_service,
            target,
            members,
            dry_run=dry_run,
            log=log,
        )


def write_roster_target(
    sheets_service: Any,
    target: RosterTarget,
    members: Sequence[RosterMember],
    *,
    dry_run: bool,
    log: logging.Logger,
) -> None:
    write_values(
        sheets_service,
        target.spreadsheet_id,
        target.range_name,
        target.clear_range,
        roster_values(target.name, members, include_birthday=target.include_birthday),
        dry_run=dry_run,
        log=log,
    )


def write_values(
    sheets_service: Any,
    spreadsheet_id: str,
    range_name: str,
    clear_range: str,
    values: list[list[Any]],
    *,
    dry_run: bool,
    log: logging.Logger,
) -> None:
    if dry_run:
        log.info(
            "dry-run: would write %s row(s) to spreadsheet %s range %s",
            len(values),
            spreadsheet_id,
            range_name,
        )
        return
    clear_values(sheets_service, spreadsheet_id, clear_range)
    update_values(sheets_service, spreadsheet_id, range_name, values)


def ministry_roster_members(
    data: ParishSoftData,
    ministry_names: Sequence[str],
) -> list[RosterMember]:
    configured = set(ministry_names)
    members = []
    for member in data.members.values():
        ministries = member.get("py ministries", {})
        roles = [
            str(entry.get("role") or "")
            for name, entry in ministries.items()
            if name in configured
        ]
        roles = sorted(role for role in set(roles) if role)
        if roles:
            members.append(RosterMember(member=member, role=", ".join(roles)))
    return sorted(members, key=lambda item: member_sort_key(item.member))


def workgroup_roster_members(
    data: ParishSoftData,
    workgroup_name: str,
    *,
    leader_suffix: str,
) -> list[RosterMember]:
    leader_name = f"{workgroup_name}{leader_suffix}"
    members = []
    for member in data.members.values():
        workgroups = member.get("py workgroups", {})
        if leader_name in workgroups:
            members.append(RosterMember(member=member, role="Leader"))
        elif workgroup_name in workgroups:
            members.append(RosterMember(member=member, role="Member"))
    return sorted(members, key=lambda item: member_sort_key(item.member))


def roster_role_matches(role_text: str, allowed_roles: set[str]) -> bool:
    return any(role.strip() in allowed_roles for role in role_text.split(","))


def roster_values(
    title: str,
    members: Sequence[RosterMember],
    *,
    include_birthday: bool,
    now: dt.datetime | None = None,
) -> list[list[Any]]:
    timestamp = (now or dt.datetime.now()).replace(microsecond=0).isoformat(sep=" ")
    headers = ["Member name", "Address", "Phone / email"]
    if include_birthday:
        headers.append("Birthday")
    headers.append("Role")
    rows: list[list[Any]] = [
        [f"Ministry: {title}"],
        [f"Last updated: {timestamp}"],
        [],
        headers,
    ]
    for roster_member in sorted(members, key=lambda item: member_sort_key(item.member)):
        member = roster_member.member
        row = [
            member.get("py friendly name LF") or member_display_name(member),
            member_address(member),
            member_contact(member),
        ]
        if include_birthday:
            row.append(member_birthday(member))
        row.append(roster_member.role)
        rows.append(row)
    return rows


def member_sort_key(member: Mapping[str, Any]) -> str:
    name = member.get("py friendly name LF") or member_display_name(member)
    return f"{name} {member.get('memberDUID', '')}"


def member_display_name(member: Mapping[str, Any]) -> str:
    first = str(member.get("firstName") or "")
    last = str(member.get("lastName") or "")
    return f"{last}, {first}".strip(", ")


def member_address(member: Mapping[str, Any]) -> str:
    family = member.get("py family") or {}
    parts = [
        family.get("primaryAddress1"),
        family.get("primaryAddress2"),
        city_state_zip(family),
    ]
    return "\n".join(str(part) for part in parts if part)


def city_state_zip(family: Mapping[str, Any]) -> str:
    city = family.get("primaryCity")
    state = family.get("primaryState")
    postal_code = family.get("primaryPostalCode")
    city_state = ", ".join(str(part) for part in (city, state) if part)
    if postal_code:
        return f"{city_state} {postal_code}".strip()
    return city_state


def member_contact(member: dict[str, Any]) -> str:
    values = [
        f"{phone['number']} {phone['type']}"
        for phone in get_member_public_phones(member)
    ]
    email = get_member_public_email(member)
    if email:
        values.append(email)
    return "\n".join(values)


def member_birthday(member: Mapping[str, Any]) -> str:
    value = member.get("birthdate")
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return f"{value.strftime('%B')} {value.day}"
    return ""


def _target(
    value: Any,
    name: str,
    *,
    source_key: str,
    plural_source_key: str | None,
    source_type: str,
    default_spreadsheet_id: str | None,
    default_range: str | None,
    default_clear_range: str | None,
) -> RosterTarget:
    item = _mapping(value, name)
    source_names = _source_names(item, name, source_key, plural_source_key)
    target_name = _optional_string(item.get("name"), f"{name}.name") or ", ".join(
        source_names
    )
    spreadsheet_id = _target_spreadsheet_id(item, name, default_spreadsheet_id)
    range_name = _optional_string(item.get("range"), f"{name}.range") or (
        default_range or DEFAULT_RANGE
    )
    clear_range = _optional_string(item.get("clear_range"), f"{name}.clear_range") or (
        default_clear_range or DEFAULT_CLEAR_RANGE
    )
    include_birthday = _bool(
        item.get("include_birthday", item.get("birthday", False)),
        f"{name}.include_birthday",
    )
    role_sheets_value = item.get("role_sheets", item.get("role sheets", []))
    role_sheets = tuple(
        _role_target(
            role_sheet,
            f"{name}.role_sheets[{index}]",
            default_spreadsheet_id=spreadsheet_id,
            default_range=range_name,
            default_clear_range=clear_range,
        )
        for index, role_sheet in enumerate(
            _list(role_sheets_value, f"{name}.role_sheets")
        )
    )
    return RosterTarget(
        name=target_name,
        source_type=source_type,
        source_names=tuple(source_names),
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        clear_range=clear_range,
        include_birthday=include_birthday,
        role_sheets=role_sheets,
    )


def _role_target(
    value: Any,
    name: str,
    *,
    default_spreadsheet_id: str,
    default_range: str,
    default_clear_range: str,
) -> RoleRosterTarget:
    item = _mapping(value, name)
    role_name = _required_string(item.get("name"), f"{name}.name")
    roles = tuple(_string_list(item.get("roles"), f"{name}.roles"))
    spreadsheet_id = _target_spreadsheet_id(item, name, default_spreadsheet_id)
    range_name = _optional_string(item.get("range"), f"{name}.range") or default_range
    clear_range = (
        _optional_string(item.get("clear_range"), f"{name}.clear_range")
        or default_clear_range
    )
    return RoleRosterTarget(
        name=role_name,
        roles=roles,
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        clear_range=clear_range,
    )


def _source_names(
    item: Mapping[str, Any],
    name: str,
    source_key: str,
    plural_source_key: str | None,
) -> list[str]:
    singular = item.get(source_key)
    plural = item.get(plural_source_key) if plural_source_key else None
    if singular and plural:
        raise ConfigError(
            f"{name} must not set both {source_key} and {plural_source_key}"
        )
    if singular is not None:
        return [_required_string(singular, f"{name}.{source_key}")]
    if plural_source_key:
        return _string_list(plural, f"{name}.{plural_source_key}")
    raise ConfigError(f"{name}.{source_key} is required")


def _target_spreadsheet_id(
    item: Mapping[str, Any],
    name: str,
    default_spreadsheet_id: str | None,
) -> str:
    value = item.get("spreadsheet_id", item.get("gsheet_id", default_spreadsheet_id))
    return _required_string(value, f"{name}.spreadsheet_id")


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
    if not value:
        raise ConfigError(f"{name} must not be empty")
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
