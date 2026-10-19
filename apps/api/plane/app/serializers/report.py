# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import SavedReport, WorkspaceDashboard, WorkspaceDashboardWidget
from plane.utils.reporting.config import DateRangeSerializer, ReportQueryConfigSerializer

from .base import BaseSerializer

PALETTES = ("modern", "horizon", "earthen")
CHART_TYPES = ("bar", "stacked_bar", "line", "area", "pie", "donut", "table")


def validated_config(config, widget_type=None):
    """Validate a report query config and return its JSON-safe representation."""
    serializer = ReportQueryConfigSerializer(data=config or {}, context={"widget_type": widget_type})
    if not serializer.is_valid():
        raise serializers.ValidationError({"config": serializer.errors})
    return serializer.data


class DisplaySerializer(serializers.Serializer):
    palette = serializers.ChoiceField(choices=PALETTES, default="modern")
    show_legend = serializers.BooleanField(default=True)
    show_values = serializers.BooleanField(default=False)
    chart_type = serializers.ChoiceField(choices=CHART_TYPES, required=False)


def validated_display(display):
    serializer = DisplaySerializer(data=display or {})
    if not serializer.is_valid():
        raise serializers.ValidationError({"display": serializer.errors})
    return serializer.data


class DashboardFiltersSerializer(serializers.Serializer):
    project_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=500)
    date_range = DateRangeSerializer(required=False, allow_null=True)


class WorkspaceDashboardWidgetSerializer(BaseSerializer):
    class Meta:
        model = WorkspaceDashboardWidget
        fields = [
            "id",
            "dashboard",
            "name",
            "widget_type",
            "size",
            "sort_order",
            "config",
            "display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["dashboard", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        widget_type = attrs.get("widget_type", getattr(instance, "widget_type", None))
        if "config" in attrs or "widget_type" in attrs:
            config = attrs.get("config", getattr(instance, "config", {}))
            attrs["config"] = validated_config(config, widget_type)
        if "display" in attrs:
            attrs["display"] = validated_display(attrs["display"])
        return attrs


class WorkspaceDashboardSerializer(BaseSerializer):
    widget_count = serializers.IntegerField(read_only=True, required=False)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceDashboard
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "logo_props",
            "access",
            "owned_by",
            "sort_order",
            "filters",
            "widget_count",
            "is_owner",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "owned_by", "created_at", "updated_at"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owned_by_id == request.user.id)

    def validate_filters(self, value):
        serializer = DashboardFiltersSerializer(data=value or {})
        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)
        return serializer.data


class SavedReportSerializer(BaseSerializer):
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = SavedReport
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "access",
            "owned_by",
            "report_type",
            "config",
            "display",
            "sort_order",
            "is_owner",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "owned_by", "report_type", "created_at", "updated_at"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owned_by_id == request.user.id)

    def validate_config(self, value):
        return validated_config(value)

    def validate_display(self, value):
        return validated_display(value)
