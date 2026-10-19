# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validation and normalisation of report query configurations."""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from rest_framework import serializers

METRIC_COUNT = "WORK_ITEM_COUNT"
METRIC_POINTS = "ESTIMATE_POINT_COUNT"
METRICS = (METRIC_COUNT, METRIC_POINTS)

CATEGORY_DIMENSIONS = (
    "STATES",
    "STATE_GROUPS",
    "LABELS",
    "ASSIGNEES",
    "ESTIMATE_POINTS",
    "CYCLES",
    "MODULES",
    "PRIORITY",
    "CREATED_BY",
    "PROJECTS",
)
DATE_DIMENSIONS = ("START_DATE", "TARGET_DATE", "CREATED_AT", "COMPLETED_AT")
DIMENSIONS = CATEGORY_DIMENSIONS + DATE_DIMENSIONS

DATE_GROUPINGS = ("DAY", "WEEK", "MONTH", "YEAR")
DATE_RANGE_FIELDS = ("created_at", "completed_at", "start_date", "target_date")
DATE_RANGE_PRESETS = (
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "this_month",
    "last_month",
    "this_quarter",
    "this_year",
    "custom",
)

WIDGET_TYPES = ("number", "bar", "stacked_bar", "line", "area", "pie", "donut", "table")
CHART_TYPES_REQUIRING_AXIS = ("bar", "stacked_bar", "line", "area", "pie", "donut")
SINGLE_SERIES_TYPES = ("pie", "donut")

TABLE_COLUMNS = (
    "sequence_id",
    "project_identifier",
    "name",
    "state_name",
    "state_group",
    "priority",
    "assignees",
    "labels",
    "start_date",
    "target_date",
    "completed_at",
    "created_at",
    "estimate",
)
TABLE_ORDER_BY = (
    "created_at",
    "-created_at",
    "target_date",
    "-target_date",
    "completed_at",
    "-completed_at",
    "sequence_id",
    "-sequence_id",
    "name",
    "-name",
)
DEFAULT_TABLE_COLUMNS = ["sequence_id", "project_identifier", "name", "state_name", "priority", "assignees", "target_date"]
TABLE_MAX_LIMIT = 100
MAX_DAILY_RANGE_DAYS = 731


def normalize_filters(node: Any) -> Any:
    """Convert list values to the comma separated strings django-filter "in"/"range" filters expect.

    The rich filter backend serialises list values as repeated query keys, which
    CSV based filters would read as a single (last) value.
    """
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in ("and", "or"):
                out[key] = [normalize_filters(child) for child in value] if isinstance(value, list) else value
            elif key == "not":
                out[key] = normalize_filters(value)
            elif isinstance(value, (list, tuple)):
                out[key] = ",".join(str(v) for v in value)
            else:
                out[key] = value
        return out
    return node


class DateRangeSerializer(serializers.Serializer):
    field = serializers.ChoiceField(choices=DATE_RANGE_FIELDS, default="created_at")
    preset = serializers.ChoiceField(choices=DATE_RANGE_PRESETS, required=False, allow_null=True)
    start = serializers.DateField(required=False, allow_null=True)
    end = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        preset = attrs.get("preset")
        if preset in (None, "custom") and not (attrs.get("start") or attrs.get("end")):
            raise serializers.ValidationError({"start": "A start or end date is required for a custom range."})
        if attrs.get("start") and attrs.get("end") and attrs["start"] > attrs["end"]:
            raise serializers.ValidationError({"end": "End date must be on or after the start date."})
        return attrs


class TableConfigSerializer(serializers.Serializer):
    columns = serializers.ListField(
        child=serializers.ChoiceField(choices=TABLE_COLUMNS), required=False, max_length=len(TABLE_COLUMNS)
    )
    order_by = serializers.ChoiceField(choices=TABLE_ORDER_BY, default="-created_at")
    limit = serializers.IntegerField(min_value=1, max_value=TABLE_MAX_LIMIT, default=20)


class ReportQueryConfigSerializer(serializers.Serializer):
    """Validates a report/widget query. Pass context={"widget_type": ...} for widget rules."""

    metric = serializers.ChoiceField(choices=METRICS, default=METRIC_COUNT)
    x_axis = serializers.ChoiceField(choices=DIMENSIONS, required=False, allow_null=True)
    group_by = serializers.ChoiceField(choices=DIMENSIONS, required=False, allow_null=True)
    date_grouping = serializers.ChoiceField(choices=DATE_GROUPINGS, required=False, allow_null=True)
    project_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=500)
    filters = serializers.JSONField(required=False)
    date_range = DateRangeSerializer(required=False, allow_null=True)
    include_sub_work_items = serializers.BooleanField(default=True)
    table = TableConfigSerializer(required=False, allow_null=True)

    def validate_filters(self, value):
        if value in (None, "", {}):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be an object.")
        return normalize_filters(value)

    def validate(self, attrs):
        widget_type = self.context.get("widget_type")
        x_axis, group_by = attrs.get("x_axis"), attrs.get("group_by")

        if group_by and not x_axis:
            raise serializers.ValidationError({"group_by": "Group by needs a dimension."})
        if group_by and group_by == x_axis:
            raise serializers.ValidationError({"group_by": "Group by must differ from the dimension."})

        if widget_type in CHART_TYPES_REQUIRING_AXIS and not x_axis:
            raise serializers.ValidationError({"x_axis": "This chart type needs a dimension."})
        if widget_type in SINGLE_SERIES_TYPES and group_by:
            raise serializers.ValidationError({"group_by": "Pie and donut charts cannot be grouped."})
        if widget_type == "number":
            attrs["x_axis"] = None
            attrs["group_by"] = None
        if widget_type == "table":
            attrs["x_axis"] = None
            attrs["group_by"] = None
            attrs["table"] = attrs.get("table") or {"order_by": "-created_at", "limit": 20}
            if not attrs["table"].get("columns"):
                attrs["table"]["columns"] = list(DEFAULT_TABLE_COLUMNS)

        uses_date_axis = x_axis in DATE_DIMENSIONS or group_by in DATE_DIMENSIONS
        if uses_date_axis:
            attrs["date_grouping"] = attrs.get("date_grouping") or "MONTH"
        else:
            attrs["date_grouping"] = None

        if attrs["date_grouping"] == "DAY" and attrs.get("date_range"):
            start, end = resolve_date_range(attrs["date_range"])[1:]
            if start and end and (end - start).days > MAX_DAILY_RANGE_DAYS:
                raise serializers.ValidationError({"date_grouping": "Daily grouping supports up to two years."})
        return attrs


@dataclass
class ReportQueryConfig:
    metric: str = METRIC_COUNT
    x_axis: Optional[str] = None
    group_by: Optional[str] = None
    date_grouping: Optional[str] = None
    project_ids: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    date_range: Optional[Dict[str, Any]] = None
    include_sub_work_items: bool = True
    table: Optional[Dict[str, Any]] = None

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], widget_type: Optional[str] = None) -> "ReportQueryConfig":
        serializer = ReportQueryConfigSerializer(data=payload or {}, context={"widget_type": widget_type})
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data["project_ids"] = [str(pid) for pid in data.get("project_ids") or []]
        data["filters"] = data.get("filters") or {}
        return cls(**data)


def _quarter_start(day: date) -> date:
    return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)


def resolve_date_range(date_range: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[date], Optional[date]]:
    """Return (field, start, end) for a date range config, in the active timezone."""
    if not date_range:
        return None, None, None
    field_name = date_range.get("field") or "created_at"
    preset = date_range.get("preset")
    today = timezone.localdate()

    if preset == "last_7_days":
        return field_name, today - timedelta(days=6), today
    if preset == "last_30_days":
        return field_name, today - timedelta(days=29), today
    if preset == "last_90_days":
        return field_name, today - timedelta(days=89), today
    if preset == "this_month":
        return field_name, today.replace(day=1), today
    if preset == "last_month":
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        return field_name, last_day_prev.replace(day=1), last_day_prev
    if preset == "this_quarter":
        return field_name, _quarter_start(today), today
    if preset == "this_year":
        return field_name, date(today.year, 1, 1), today

    start, end = date_range.get("start"), date_range.get("end")
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    return field_name, start, end


def month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])
