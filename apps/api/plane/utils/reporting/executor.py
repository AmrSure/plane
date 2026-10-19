# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Turns a ReportQueryConfig into chart, number or table results.

Design notes
  * The set of matching work items is computed first (scope + filters + date range)
    and aggregation runs on a fresh queryset restricted by id, so joins added by
    filters can never inflate a sum.
  * Many-to-many dimensions (labels, assignees, cycles, modules) use a single
    FilteredRelation join that excludes soft-deleted links, then (bucket, work item)
    pairs are de-duplicated before aggregating. Counts and estimate-point sums are
    therefore exact even when a work item falls into several buckets.
  * Estimate points only count estimates of type "points" whose value is numeric.
"""

import contextlib
from collections import OrderedDict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import OperationalError, connection, transaction
from django.db.models import DateField, F, FilteredRelation, Q, QuerySet
from django.db.models.functions import Trunc
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from plane.db.models import Issue
from plane.utils.filters import ComplexFilterBackend, IssueFilterSet

from .config import DATE_DIMENSIONS, METRIC_POINTS, ReportQueryConfig, resolve_date_range
from .scope import scoped_issue_queryset, scoped_project_count

MAX_CATEGORY_BUCKETS = 100
MAX_SEGMENTS = 25
MAX_SOURCE_ROWS = 250_000
STATEMENT_TIMEOUT_MS = 15_000

PRIORITY_ORDER = ["urgent", "high", "medium", "low", "none"]
STATE_GROUP_ORDER = ["backlog", "unstarted", "started", "completed", "cancelled"]


class QueryTimeout(Exception):
    """The report query exceeded the statement timeout."""


class _FilterView:
    """Minimal view object for ComplexFilterBackend: it only needs a filterset class."""

    filterset_class = IssueFilterSet
    complex_filter_max_depth = 5


# --------------------------------------------------------------------------- dimensions

# Relations reached through soft-deletable through tables.
RELATIONS = {
    "LABELS": ("rpt_label", "label_issue"),
    "ASSIGNEES": ("rpt_assignee", "issue_assignee"),
    "CYCLES": ("rpt_cycle", "issue_cycle"),
    "MODULES": ("rpt_module", "issue_module"),
}

# dimension -> (key field, name field, color field or None)
FIELDS = {
    "STATES": ("state_id", "state__name", "state__color"),
    "STATE_GROUPS": ("state__group", "state__group", None),
    "PRIORITY": ("priority", "priority", None),
    "PROJECTS": ("project_id", "project__name", None),
    "CREATED_BY": ("created_by_id", "created_by__display_name", None),
    "ESTIMATE_POINTS": ("estimate_point__value", "estimate_point__value", None),
    "LABELS": ("rpt_label__label_id", "rpt_label__label__name", "rpt_label__label__color"),
    "ASSIGNEES": ("rpt_assignee__assignee_id", "rpt_assignee__assignee__display_name", None),
    "CYCLES": ("rpt_cycle__cycle_id", "rpt_cycle__cycle__name", None),
    "MODULES": ("rpt_module__module_id", "rpt_module__module__name", None),
}

DATE_FIELDS = {
    "START_DATE": ("start_date", False),
    "TARGET_DATE": ("target_date", False),
    "CREATED_AT": ("created_at", True),
    "COMPLETED_AT": ("completed_at", True),
}

TRUNC_KIND = {"DAY": "day", "WEEK": "week", "MONTH": "month", "YEAR": "year"}


def _with_relation(qs: QuerySet, dimension: Optional[str]) -> QuerySet:
    if dimension in RELATIONS:
        alias, relation = RELATIONS[dimension]
        qs = qs.annotate(
            **{alias: FilteredRelation(relation, condition=Q(**{f"{relation}__deleted_at__isnull": True}))}
        )
    return qs


def _dimension_annotations(prefix: str, dimension: str, date_grouping: Optional[str]) -> Dict[str, Any]:
    """Annotations producing <prefix>_key, <prefix>_name and optionally <prefix>_color."""
    if dimension in DATE_DIMENSIONS:
        field_name, is_datetime = DATE_FIELDS[dimension]
        kind = TRUNC_KIND[date_grouping or "MONTH"]
        if is_datetime:
            expr = Trunc(field_name, kind, output_field=DateField(), tzinfo=timezone.get_current_timezone())
        else:
            expr = Trunc(field_name, kind, output_field=DateField())
        return {f"{prefix}_key": expr}

    key_field, name_field, color_field = FIELDS[dimension]
    annotations = {f"{prefix}_key": F(key_field), f"{prefix}_name": F(name_field)}
    if color_field:
        annotations[f"{prefix}_color"] = F(color_field)
    return annotations


# --------------------------------------------------------------------------- selection


def _merge_project_ids(config_ids: List[str], override_ids: Optional[Iterable]) -> Optional[List[str]]:
    override = [str(pid) for pid in override_ids or []]
    if config_ids and override:
        merged = [pid for pid in config_ids if pid in set(override)]
        return merged or ["00000000-0000-0000-0000-000000000000"]
    return config_ids or override or None


def _apply_date_range(qs: QuerySet, date_range: Optional[Dict[str, Any]]) -> QuerySet:
    field_name, start, end = resolve_date_range(date_range)
    if not field_name:
        return qs
    lookup = f"{field_name}__date" if field_name in ("created_at", "completed_at") else field_name
    if start:
        qs = qs.filter(**{f"{lookup}__gte": start})
    if end:
        qs = qs.filter(**{f"{lookup}__lte": end})
    return qs


def matching_issue_ids(user, slug: str, cfg: ReportQueryConfig, overrides: Optional[Dict] = None) -> QuerySet:
    """Ids of work items matching the config that the user is allowed to see."""
    overrides = overrides or {}
    project_ids = _merge_project_ids(cfg.project_ids, overrides.get("project_ids"))
    qs = scoped_issue_queryset(user, slug, project_ids)
    if cfg.filters:
        qs = ComplexFilterBackend().filter_queryset(None, qs, _FilterView(), filter_data=cfg.filters)
    qs = _apply_date_range(qs, overrides.get("date_range") or cfg.date_range)
    if not cfg.include_sub_work_items:
        qs = qs.filter(parent__isnull=True)
    return qs.values("id")


def _base_queryset(ids: QuerySet) -> QuerySet:
    return Issue.issue_objects.filter(id__in=ids)


# --------------------------------------------------------------------------- execution helpers


@contextlib.contextmanager
def statement_timeout(milliseconds: int = STATEMENT_TIMEOUT_MS):
    """Bound the runtime of report queries; raises QueryTimeout when exceeded."""
    try:
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL statement_timeout = {int(milliseconds)}")
            yield
    except OperationalError as exc:
        if "statement timeout" in str(exc) or "canceling statement" in str(exc):
            raise QueryTimeout() from exc
        raise


def _points_value(raw_value: Optional[str], estimate_type: Optional[str]) -> float:
    if estimate_type != "points" or raw_value in (None, ""):
        return 0.0
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def _key_str(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _name_str(value: Any, key: str) -> str:
    if value is None or value == "":
        return "none" if key == "none" else key
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _metric_value(ids: set, points: Dict[Any, float], metric: str) -> float:
    if metric == METRIC_POINTS:
        return round(sum(points.get(i, 0.0) for i in ids), 2)
    return len(ids)


def _sort_buckets(dimension: str, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if dimension in DATE_DIMENSIONS:
        return sorted(buckets, key=lambda b: (b["key"] == "none", b["key"]))
    if dimension == "PRIORITY":
        order = {p: i for i, p in enumerate(PRIORITY_ORDER)}
        return sorted(buckets, key=lambda b: order.get(b["key"], len(order)))
    if dimension == "STATE_GROUPS":
        order = {g: i for i, g in enumerate(STATE_GROUP_ORDER)}
        return sorted(buckets, key=lambda b: order.get(b["key"], len(order)))
    return sorted(buckets, key=lambda b: (b["key"] == "none", -b["count"], b["name"].lower()))


def _fetch_rows(qs: QuerySet, values: List[str]) -> List[Dict[str, Any]]:
    rows = list(qs.values(*values).distinct()[: MAX_SOURCE_ROWS + 1])
    if len(rows) > MAX_SOURCE_ROWS:
        raise ValidationError({"code": "too_many_rows", "message": "Narrow the filters to run this report."})
    return rows


def _meta(user, slug: str, cfg: ReportQueryConfig, overrides: Optional[Dict], **extra) -> Dict[str, Any]:
    project_ids = _merge_project_ids(cfg.project_ids, (overrides or {}).get("project_ids"))
    meta = {
        "metric": cfg.metric,
        "x_axis": cfg.x_axis,
        "group_by": cfg.group_by,
        "date_grouping": cfg.date_grouping,
        "project_count": scoped_project_count(user, slug, project_ids),
        "generated_at": timezone.now().isoformat(),
        "truncated": False,
    }
    meta.update(extra)
    return meta


# --------------------------------------------------------------------------- public API


def execute_number(user, slug: str, cfg: ReportQueryConfig, overrides: Optional[Dict] = None) -> Dict[str, Any]:
    with statement_timeout():
        qs = _base_queryset(matching_issue_ids(user, slug, cfg, overrides))
        rows = _fetch_rows(qs, ["id", "estimate_point__value", "estimate_point__estimate__type"])
    points = {r["id"]: _points_value(r["estimate_point__value"], r["estimate_point__estimate__type"]) for r in rows}
    ids = set(points)
    return {
        "value": _metric_value(ids, points, cfg.metric),
        "work_item_count": len(ids),
        "meta": _meta(user, slug, cfg, overrides),
    }


def execute_chart(user, slug: str, cfg: ReportQueryConfig, overrides: Optional[Dict] = None) -> Dict[str, Any]:
    if not cfg.x_axis:
        raise ValidationError({"x_axis": "A dimension is required for charts."})

    with statement_timeout():
        qs = _base_queryset(matching_issue_ids(user, slug, cfg, overrides))
        qs = _with_relation(qs, cfg.x_axis)
        qs = _with_relation(qs, cfg.group_by)
        annotations = _dimension_annotations("x", cfg.x_axis, cfg.date_grouping)
        if cfg.group_by:
            annotations.update(_dimension_annotations("g", cfg.group_by, cfg.date_grouping))
        qs = qs.annotate(**annotations)
        values = list(annotations.keys()) + ["id", "estimate_point__value", "estimate_point__estimate__type"]
        rows = _fetch_rows(qs, values)

    points: Dict[Any, float] = {}
    buckets: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    segment_names: Dict[str, str] = {}
    segment_ids: Dict[str, set] = {}

    for row in rows:
        points[row["id"]] = _points_value(row["estimate_point__value"], row["estimate_point__estimate__type"])
        x_key = _key_str(row["x_key"])
        bucket = buckets.get(x_key)
        if bucket is None:
            bucket = {
                "key": x_key,
                "name": _name_str(row.get("x_name", row["x_key"]), x_key),
                "ids": set(),
                "segments": {},
            }
            if row.get("x_color"):
                bucket["color"] = row["x_color"]
            buckets[x_key] = bucket
        bucket["ids"].add(row["id"])

        if cfg.group_by:
            g_key = _key_str(row["g_key"])
            segment_names.setdefault(g_key, _name_str(row.get("g_name", row["g_key"]), g_key))
            bucket["segments"].setdefault(g_key, set()).add(row["id"])
            segment_ids.setdefault(g_key, set()).add(row["id"])

    truncated = False

    # Keep the largest segments; fold the rest into "other".
    kept_segments = list(segment_names.keys())
    if len(kept_segments) > MAX_SEGMENTS:
        truncated = True
        ranked = sorted(kept_segments, key=lambda k: -_metric_value(segment_ids[k], points, cfg.metric))
        kept = set(ranked[: MAX_SEGMENTS - 1])
        for bucket in buckets.values():
            other = set()
            for g_key in list(bucket["segments"].keys()):
                if g_key not in kept:
                    other |= bucket["segments"].pop(g_key)
            if other:
                bucket["segments"]["other"] = other
        segment_names = {k: v for k, v in segment_names.items() if k in kept}
        segment_names["other"] = "other"

    data = []
    for bucket in buckets.values():
        item = {"key": bucket["key"], "name": bucket["name"], "count": _metric_value(bucket["ids"], points, cfg.metric)}
        if "color" in bucket:
            item["color"] = bucket["color"]
        for g_key, ids in bucket["segments"].items():
            item[g_key] = _metric_value(ids, points, cfg.metric)
        item["_ids"] = bucket["ids"]
        item["_segs"] = bucket["segments"]
        data.append(item)

    data = _sort_buckets(cfg.x_axis, data)

    # Cap category buckets; fold the tail into "other".
    if cfg.x_axis not in DATE_DIMENSIONS and len(data) > MAX_CATEGORY_BUCKETS:
        truncated = True
        head, tail = data[: MAX_CATEGORY_BUCKETS - 1], data[MAX_CATEGORY_BUCKETS - 1 :]
        other_ids = set().union(*(b["_ids"] for b in tail))
        other = {"key": "other", "name": "other", "count": _metric_value(other_ids, points, cfg.metric)}
        for g_key in segment_names:
            seg_ids = set().union(*(b["_segs"].get(g_key, set()) for b in tail))
            if seg_ids:
                other[g_key] = _metric_value(seg_ids, points, cfg.metric)
        data = head + [other]

    all_ids = set(points)
    for item in data:
        item.pop("_ids", None)
        item.pop("_segs", None)

    return {
        "data": data,
        "schema": segment_names,
        "totals": {"value": _metric_value(all_ids, points, cfg.metric), "work_item_count": len(all_ids)},
        "meta": _meta(user, slug, cfg, overrides, truncated=truncated),
    }


TABLE_FIELD_MAP = {
    "sequence_id": "sequence_id",
    "project_identifier": "project__identifier",
    "name": "name",
    "state_name": "state__name",
    "state_group": "state__group",
    "priority": "priority",
    "start_date": "start_date",
    "target_date": "target_date",
    "completed_at": "completed_at",
    "created_at": "created_at",
    "estimate": "estimate_point__value",
}


def execute_table(
    user, slug: str, cfg: ReportQueryConfig, overrides: Optional[Dict] = None, limit: Optional[int] = None
) -> Dict[str, Any]:
    table = cfg.table or {}
    columns = table.get("columns") or ["sequence_id", "name"]
    order_by = table.get("order_by") or "-created_at"
    limit = limit or table.get("limit") or 20

    with statement_timeout():
        ids = matching_issue_ids(user, slug, cfg, overrides)
        qs = _base_queryset(ids)
        total_count = qs.count()

        # Identifier fields are always needed to render and link work item IDs
        values = ["id", "project_id", "state__color", "sequence_id", "project__identifier"] + [
            TABLE_FIELD_MAP[c] for c in columns if c in TABLE_FIELD_MAP
        ]
        annotations = {}
        if "assignees" in columns:
            qs = _with_relation(qs, "ASSIGNEES")
            annotations["assignee_ids"] = ArrayAgg(
                "rpt_assignee__assignee_id", distinct=True, filter=Q(rpt_assignee__assignee_id__isnull=False)
            )
            annotations["assignee_names"] = ArrayAgg(
                "rpt_assignee__assignee__display_name",
                distinct=True,
                filter=Q(rpt_assignee__assignee_id__isnull=False),
            )
        if "labels" in columns:
            qs = _with_relation(qs, "LABELS")
            annotations["label_names"] = ArrayAgg(
                "rpt_label__label__name", distinct=True, filter=Q(rpt_label__label_id__isnull=False)
            )
        rows = list(
            qs.values(*dict.fromkeys(values)).annotate(**annotations).order_by(order_by, "-id")[:limit]
            if annotations
            else qs.values(*dict.fromkeys(values)).order_by(order_by, "-id")[:limit]
        )

    results = []
    for row in rows:
        item = {
            "id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "state_color": row.get("state__color"),
            "sequence_id": row.get("sequence_id"),
            "project_identifier": row.get("project__identifier"),
        }
        for column in columns:
            if column == "assignees":
                item["assignee_ids"] = [str(a) for a in row.get("assignee_ids") or []]
                item["assignees"] = sorted(n for n in row.get("assignee_names") or [] if n)
            elif column == "labels":
                item["labels"] = sorted(n for n in row.get("label_names") or [] if n)
            else:
                value = row.get(TABLE_FIELD_MAP[column])
                item[column] = value.isoformat() if isinstance(value, (date, datetime)) else value
        results.append(item)

    return {
        "results": results,
        "total_count": total_count,
        "meta": _meta(user, slug, cfg, overrides, truncated=total_count > len(results), columns=columns),
    }


def to_export_rows(
    chart: Dict[str, Any], dimension_label: str, total_label: str, value_labels: Optional[Dict[str, str]] = None
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Pivot a chart result into (headers, rows) for CSV/XLSX export."""
    value_labels = value_labels or {}

    def label(raw: str) -> str:
        return value_labels.get(raw, raw)

    schema = chart.get("schema") or {}
    segment_headers = [(key, label(name)) for key, name in schema.items()]
    headers = [dimension_label] + [h for _, h in segment_headers] + [total_label]
    rows = []
    for item in chart.get("data", []):
        row = {dimension_label: label(item.get("name", item.get("key")))}
        for key, header in segment_headers:
            row[header] = item.get(key, 0)
        row[total_label] = item.get("count", 0)
        rows.append(row)
    return headers, rows
