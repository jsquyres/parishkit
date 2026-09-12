"""Namespaced scaffold; ingress isolation is additionally owned by ARC-03/OPS-01."""

from django.urls import include, path

from . import views
from .accounts import (
    access_gate,
    authentication,
    campaign_views,
    code_reports,
    content_views,
    family_authentication,
    ministry_views,
    parish_views,
    presence,
    schedule_views,
    share_views,
)
from .jobs import views as job_views

public_patterns = [
    path("", family_authentication.entry, name="entry"),
    path("access/<str:token>", family_authentication.access, name="access"),
]
family_patterns = [
    path("presence", presence.heartbeat, name="presence"),
    path("", family_authentication.portal, name="entry"),
    path("keepalive", family_authentication.keepalive, name="keepalive"),
    path("logout", family_authentication.logout, name="logout"),
]
admin_patterns = [
    path(
        "campaign/<uuid:campaign_id>/schedules",
        schedule_views.schedule_settings,
        name="schedule_settings",
    ),
    path(
        "campaign/<uuid:campaign_id>/content",
        content_views.content_settings,
        name="content_catalog",
    ),
    path(
        "campaign/<uuid:campaign_id>/content/<str:kind>/<str:slot>",
        content_views.content_settings,
        name="content_edit",
    ),
    path(
        "campaign/<uuid:campaign_id>/content/<str:kind>/<str:slot>/<uuid:revision_id>",
        content_views.content_settings,
        name="content_revision",
    ),
    path("presence", presence.active_families, name="presence"),
    path(
        "campaign/<uuid:campaign_id>/share-options",
        share_views.share_settings,
        name="share_settings",
    ),
    path("campaign/new", campaign_views.campaign_settings, name="campaign_new"),
    path(
        "campaign/<uuid:campaign_id>/settings",
        campaign_views.campaign_settings,
        name="campaign_settings",
    ),
    path("configuration/parish", parish_views.parish_settings, name="parish_settings"),
    path(
        "configuration/ministries", ministry_views.ministry_activity, name="ministries"
    ),
    path(
        "configuration/requests/<uuid:request_id>",
        ministry_views.configuration_request,
        name="configuration_request",
    ),
    path("background", job_views.background_page, name="background"),
    path(
        "background/task/<uuid:task_id>",
        job_views.task_page,
        name="background_task_page",
    ),
    path("background/tasks", job_views.task_list, name="background_tasks"),
    path(
        "background/tasks/<uuid:task_id>",
        job_views.task_detail,
        name="background_task",
    ),
    path("setup", access_gate.setup, name="setup"),
    path("maintenance", access_gate.maintenance, name="maintenance"),
    path(
        "campaign/<uuid:campaign_id>/family-codes",
        code_reports.family_codes,
        name="family_codes",
    ),
    path("", authentication.index, name="index"),
    path("login", authentication.login, name="login"),
    path("logout", authentication.logout, name="logout"),
]
internal_patterns = [
    path("health/live", views.live, name="live"),
    path("health/ready", views.ready, name="ready"),
    path("metrics", views.metrics, name="metrics"),
]
urlpatterns = [
    path("admin/oauth/callback", authentication.callback, name="google_callback"),
    path("admin/oauth/start", authentication.login, name="google_login"),
    path("", include((public_patterns, "public"))),
    path("family/", include((family_patterns, "family"))),
    path("admin/", include((admin_patterns, "admin"))),
    path("", include((internal_patterns, "internal"))),
]
