# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from .base import BaseModel

ACCESS_CHOICES = ((0, "Private"), (1, "Workspace"))


class WorkspaceDashboard(BaseModel):
    """A user-built dashboard of report widgets, private to its owner or shared with the workspace."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workspace_dashboards")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo_props = models.JSONField(default=dict)
    access = models.PositiveSmallIntegerField(choices=ACCESS_CHOICES, default=0)
    owned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_workspace_dashboards"
    )
    sort_order = models.FloatField(default=65535)
    # Dashboard-level overrides applied to every widget: {"project_ids": [...], "date_range": {...}}
    filters = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Workspace Dashboard"
        verbose_name_plural = "Workspace Dashboards"
        db_table = "workspace_dashboards"
        ordering = ("sort_order", "-created_at")
        indexes = [
            models.Index(fields=["workspace", "owned_by"], name="ws_dashboard_ws_owner_idx"),
            models.Index(fields=["workspace", "access"], name="ws_dashboard_ws_access_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(access__in=[0, 1]), name="ws_dashboard_access_valid"),
        ]

    def __str__(self):
        return f"{self.name} <{self.workspace_id}>"


class WorkspaceDashboardWidget(BaseModel):
    """A single chart, number or table on a workspace dashboard."""

    class WidgetType(models.TextChoices):
        NUMBER = "number", "Number"
        BAR = "bar", "Bar"
        STACKED_BAR = "stacked_bar", "Stacked bar"
        LINE = "line", "Line"
        AREA = "area", "Area"
        PIE = "pie", "Pie"
        DONUT = "donut", "Donut"
        TABLE = "table", "Table"

    class WidgetSize(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"
        FULL = "full", "Full"

    workspace = models.ForeignKey(
        "db.Workspace", on_delete=models.CASCADE, related_name="workspace_dashboard_widgets"
    )
    dashboard = models.ForeignKey(WorkspaceDashboard, on_delete=models.CASCADE, related_name="widgets")
    name = models.CharField(max_length=255, blank=True)
    widget_type = models.CharField(max_length=32, choices=WidgetType.choices, default=WidgetType.BAR)
    size = models.CharField(max_length=16, choices=WidgetSize.choices, default=WidgetSize.MEDIUM)
    sort_order = models.FloatField(default=65535)
    # Report query configuration, validated by plane.utils.reporting.config.ReportQueryConfigSerializer
    config = models.JSONField(default=dict)
    # Presentation options: {"palette": "modern", "show_legend": true, ...}
    display = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Workspace Dashboard Widget"
        verbose_name_plural = "Workspace Dashboard Widgets"
        db_table = "workspace_dashboard_widgets"
        ordering = ("sort_order",)

    def __str__(self):
        return f"{self.widget_type} {self.name} <{self.dashboard_id}>"


class SavedReport(BaseModel):
    """A saved custom report configuration."""

    class ReportType(models.TextChoices):
        CUSTOM = "custom", "Custom"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="saved_reports")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    access = models.PositiveSmallIntegerField(choices=ACCESS_CHOICES, default=0)
    owned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_saved_reports")
    report_type = models.CharField(max_length=32, choices=ReportType.choices, default=ReportType.CUSTOM)
    config = models.JSONField(default=dict)
    # Presentation options: {"chart_type": "bar", "palette": "modern"}
    display = models.JSONField(default=dict)
    sort_order = models.FloatField(default=65535)

    class Meta:
        verbose_name = "Saved Report"
        verbose_name_plural = "Saved Reports"
        db_table = "saved_reports"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "owned_by"], name="saved_report_ws_owner_idx"),
            models.Index(fields=["workspace", "access"], name="saved_report_ws_access_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(access__in=[0, 1]), name="saved_report_access_valid"),
        ]

    def __str__(self):
        return f"{self.name} <{self.workspace_id}>"
