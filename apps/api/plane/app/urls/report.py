# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.report import (
    CycleReportEndpoint,
    CycleReportExportEndpoint,
    ReportExportEndpoint,
    ReportQueryEndpoint,
    SavedReportEndpoint,
    WorkspaceDashboardEndpoint,
    WorkspaceDashboardWidgetDataEndpoint,
    WorkspaceDashboardWidgetEndpoint,
    WorkspaceDashboardWidgetPreviewEndpoint,
    WorkspaceDashboardWidgetReorderEndpoint,
)

urlpatterns = [
    # Dashboards
    path("workspaces/<str:slug>/dashboards/", WorkspaceDashboardEndpoint.as_view(), name="workspace-dashboards"),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:pk>/",
        WorkspaceDashboardEndpoint.as_view(),
        name="workspace-dashboard-detail",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/",
        WorkspaceDashboardWidgetEndpoint.as_view(),
        name="workspace-dashboard-widgets",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/reorder/",
        WorkspaceDashboardWidgetReorderEndpoint.as_view(),
        name="workspace-dashboard-widgets-reorder",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/<uuid:pk>/",
        WorkspaceDashboardWidgetEndpoint.as_view(),
        name="workspace-dashboard-widget-detail",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/<uuid:pk>/data/",
        WorkspaceDashboardWidgetDataEndpoint.as_view(),
        name="workspace-dashboard-widget-data",
    ),
    path(
        "workspaces/<str:slug>/dashboard-widgets/preview/",
        WorkspaceDashboardWidgetPreviewEndpoint.as_view(),
        name="workspace-dashboard-widget-preview",
    ),
    # Reports
    path("workspaces/<str:slug>/reports/", SavedReportEndpoint.as_view(), name="saved-reports"),
    path("workspaces/<str:slug>/reports/query/", ReportQueryEndpoint.as_view(), name="report-query"),
    path("workspaces/<str:slug>/reports/export/", ReportExportEndpoint.as_view(), name="report-export"),
    path("workspaces/<str:slug>/reports/<uuid:pk>/", SavedReportEndpoint.as_view(), name="saved-report-detail"),
    # Cycle reports
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/report/",
        CycleReportEndpoint.as_view(),
        name="cycle-report",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/report/export/",
        CycleReportExportEndpoint.as_view(),
        name="cycle-report-export",
    ),
]
