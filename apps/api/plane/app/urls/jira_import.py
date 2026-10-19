# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.jira_import import (
    JiraImportDetailEndpoint,
    JiraImportEndpoint,
    JiraImportStartEndpoint,
    JiraImportUndoEndpoint,
)

urlpatterns = [
    path("workspaces/<str:slug>/jira-imports/", JiraImportEndpoint.as_view(), name="jira-imports"),
    path("workspaces/<str:slug>/jira-imports/<uuid:pk>/", JiraImportDetailEndpoint.as_view(), name="jira-import"),
    path(
        "workspaces/<str:slug>/jira-imports/<uuid:pk>/start/",
        JiraImportStartEndpoint.as_view(),
        name="jira-import-start",
    ),
    path(
        "workspaces/<str:slug>/jira-imports/<uuid:pk>/undo/",
        JiraImportUndoEndpoint.as_view(),
        name="jira-import-undo",
    ),
]
