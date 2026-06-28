"""Google Workspace Groups/Admin SDK helpers."""

from __future__ import annotations

from typing import Any

from parishkit.google.auth import build_service, execute_google_request


def build_admin_directory_service(
    credentials: Any,
    *,
    build_fn: Any | None = None,
) -> Any:
    return build_service(
        "admin", "directory_v1", credentials=credentials, build_fn=build_fn
    )


def build_groups_settings_service(
    credentials: Any,
    *,
    build_fn: Any | None = None,
) -> Any:
    return build_service(
        "groupssettings", "v1", credentials=credentials, build_fn=build_fn
    )


def list_group_members(service: Any, group_key: str) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        request = service.members().list(groupKey=group_key, pageToken=page_token)
        response = execute_google_request(request)
        members.extend(response.get("members", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return members


def get_group_posting_permissions(service: Any, group_key: str) -> str | None:
    request = service.groups().get(groupUniqueId=group_key, fields="whoCanPostMessage")
    return execute_google_request(request).get("whoCanPostMessage")


def insert_group_member(
    service: Any,
    group_key: str,
    email: str,
    role: str,
) -> None:
    request = service.members().insert(
        groupKey=group_key,
        body={"email": email, "role": role},
    )
    execute_google_request(request)


def update_group_member_role(
    service: Any,
    group_key: str,
    email: str,
    role: str,
) -> None:
    request = service.members().update(
        groupKey=group_key,
        memberKey=email,
        body={"email": email, "role": role},
    )
    execute_google_request(request)


def delete_group_member(service: Any, group_key: str, member_key: str) -> None:
    request = service.members().delete(groupKey=group_key, memberKey=member_key)
    execute_google_request(request)
