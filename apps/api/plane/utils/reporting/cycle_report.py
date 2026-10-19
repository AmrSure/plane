# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""On-demand cycle report: summary, burndown, breakdowns, scope changes, incomplete items.

Data sources
  * Live cycles use the work items currently linked to the cycle.
  * Cycles whose unfinished items were transferred carry a progress_snapshot taken at
    transfer time; summary and assignee/label breakdowns come from it, marked "snapshot".
  * Scope changes come from IssueActivity rows (field="cycles"). Moving an item between
    cycles rewrites the cycle link in place, so the activity log is the only record of
    removals. Activities are written asynchronously, so very recent changes may lag.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from django.db.models import FilteredRelation, Q
from django.utils import timezone

from plane.db.models import Cycle, Issue, IssueActivity

from .scope import scoped_issue_queryset

INCOMPLETE_LIMIT = 500
CLOSED_GROUPS = ("completed", "cancelled")
STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")
PRIORITIES = ("urgent", "high", "medium", "low", "none")


class CycleWithoutDates(Exception):
    """The cycle has no start or end date, so a report cannot be built."""


def _points(value: Optional[str], estimate_type: Optional[str]) -> Optional[float]:
    if estimate_type != "points" or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tz(cycle: Cycle) -> ZoneInfo:
    try:
        return ZoneInfo(cycle.timezone or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _local_date(value, tz: ZoneInfo) -> Optional[date]:
    if value is None:
        return None
    return value.astimezone(tz).date()


def _pct(part: float, whole: float) -> float:
    return round(part * 100.0 / whole, 1) if whole else 0.0


def _summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups = {g: 0 for g in STATE_GROUPS}
    points = {g: 0.0 for g in STATE_GROUPS}
    has_points = False
    for item in items:
        group = item["state__group"] if item["state__group"] in groups else "backlog"
        groups[group] += 1
        if item["points"] is not None:
            has_points = True
            points[group] += item["points"]
    total = len(items)
    total_points = round(sum(points.values()), 2)
    completed, cancelled = groups["completed"], groups["cancelled"]
    return {
        "total": total,
        "completed": completed,
        "cancelled": cancelled,
        "pending": total - completed - cancelled,
        "state_groups": groups,
        "completion_pct": _pct(completed, total),
        "points": (
            {
                "total": total_points,
                "completed": round(points["completed"], 2),
                "cancelled": round(points["cancelled"], 2),
                "pending": round(total_points - points["completed"] - points["cancelled"], 2),
                "completion_pct": _pct(points["completed"], total_points),
            }
            if has_points
            else None
        ),
    }


def _burndown(items, days: List[date], today: date, tz: ZoneInfo, use_points: bool) -> Dict[str, Optional[float]]:
    def weight(item):
        return (item["points"] or 0.0) if use_points else 1.0

    total = sum(weight(i) for i in items)
    completed_by_day: Dict[date, float] = defaultdict(float)
    for item in items:
        if item["state__group"] == "completed" and item["completed_at"]:
            completed_by_day[_local_date(item["completed_at"], tz)] += weight(item)

    chart, done = {}, 0.0
    before_start = sum(v for d, v in completed_by_day.items() if days and d < days[0])
    done += before_start
    for day in days:
        done += completed_by_day.get(day, 0.0)
        chart[day.isoformat()] = round(total - done, 2) if day <= today else None
    return chart


def _breakdown(items, pairs: Dict[Any, List[Dict[str, Any]]], none_label: str) -> List[Dict[str, Any]]:
    """Totals per related entity (assignee/label). pairs maps issue id -> [{id, name, color?}]."""
    rows: Dict[str, Dict[str, Any]] = {}
    for item in items:
        related = pairs.get(item["id"]) or [{"id": None, "name": none_label}]
        for entity in related:
            key = str(entity["id"]) if entity["id"] else "none"
            row = rows.setdefault(
                key,
                {
                    "id": key,
                    "name": entity.get("name") or none_label,
                    "color": entity.get("color"),
                    "total": 0,
                    "completed": 0,
                    "pending": 0,
                    "points_total": 0.0,
                    "points_completed": 0.0,
                },
            )
            row["total"] += 1
            if item["state__group"] == "completed":
                row["completed"] += 1
            elif item["state__group"] != "cancelled":
                row["pending"] += 1
            if item["points"] is not None:
                row["points_total"] += item["points"]
                if item["state__group"] == "completed":
                    row["points_completed"] += item["points"]
    return sorted(rows.values(), key=lambda r: (r["id"] == "none", -r["total"], str(r["name"]).lower()))


def _snapshot_breakdown(entries, kind: str) -> List[Dict[str, Any]]:
    rows = []
    for entry in entries or []:
        entity_id = entry.get("assignee_id") if kind == "assignees" else entry.get("label_id")
        name = entry.get("display_name") if kind == "assignees" else entry.get("label_name")
        rows.append(
            {
                "id": entity_id or "none",
                "name": name or "none",
                "color": entry.get("color"),
                "total": entry.get("total_issues", 0) or 0,
                "completed": entry.get("completed_issues", 0) or 0,
                "pending": entry.get("pending_issues", 0) or 0,
                "points_total": None,
                "points_completed": None,
            }
        )
    return rows


def _item_row(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(item["id"]),
        "sequence_id": item["sequence_id"],
        "project_identifier": item["project__identifier"],
        "name": item["name"],
        "state_name": item["state__name"],
        "state_group": item["state__group"],
        "state_color": item["state__color"],
        "priority": item["priority"],
        "target_date": item["target_date"].isoformat() if item["target_date"] else None,
        "estimate": item["estimate_point__value"],
        "assignees": item.get("assignees", []),
    }


ITEM_FIELDS = [
    "id",
    "name",
    "sequence_id",
    "project__identifier",
    "state__name",
    "state__group",
    "state__color",
    "priority",
    "target_date",
    "completed_at",
    "estimate_point__value",
    "estimate_point__estimate__type",
]


def _load_items(visible_ids) -> List[Dict[str, Any]]:
    items = list(Issue.issue_objects.filter(id__in=visible_ids).values(*ITEM_FIELDS))
    for item in items:
        item["points"] = _points(item["estimate_point__value"], item["estimate_point__estimate__type"])
    return items


def _relation_pairs(ids, relation: str, id_field: str, name_field: str, color_field: Optional[str] = None):
    qs = (
        Issue.issue_objects.filter(id__in=ids)
        .annotate(rel=FilteredRelation(relation, condition=Q(**{f"{relation}__deleted_at__isnull": True})))
        .filter(**{f"rel__{id_field}__isnull": False})
    )
    fields = ["id", f"rel__{id_field}", f"rel__{name_field}"] + ([f"rel__{color_field}"] if color_field else [])
    pairs: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in qs.values(*fields).distinct():
        pairs[row["id"]].append(
            {
                "id": row[f"rel__{id_field}"],
                "name": row[f"rel__{name_field}"],
                "color": row.get(f"rel__{color_field}") if color_field else None,
            }
        )
    return pairs


def _scope_changes(cycle: Cycle, visible_issue_ids: set, now) -> Dict[str, Any]:
    cycle_id = cycle.id
    window_end = min(cycle.end_date, now)
    activity = IssueActivity.objects.filter(project_id=cycle.project_id, field="cycles").filter(
        Q(new_identifier=cycle_id) | Q(old_identifier=cycle_id)
    )
    any_activity = activity.exists()
    events = activity.filter(created_at__gt=cycle.start_date, created_at__lte=window_end).order_by("created_at")

    last_event: Dict[Any, Dict[str, Any]] = {}
    for event in events.values("issue_id", "verb", "old_identifier", "new_identifier", "created_at"):
        if event["issue_id"] is None or event["issue_id"] not in visible_issue_ids:
            continue
        added = event["new_identifier"] == cycle_id and event["verb"] in ("created", "updated")
        last_event[event["issue_id"]] = {"added": added, "at": event["created_at"]}

    details = {
        row["id"]: row
        for row in Issue.all_objects.filter(id__in=list(last_event.keys())).values(
            "id", "name", "sequence_id", "project__identifier"
        )
    }

    def entry(issue_id, info):
        row = details.get(issue_id, {})
        return {
            "id": str(issue_id),
            "name": row.get("name"),
            "sequence_id": row.get("sequence_id"),
            "project_identifier": row.get("project__identifier"),
            "at": info["at"].isoformat(),
        }

    added = [entry(i, e) for i, e in last_event.items() if e["added"]]
    removed = [entry(i, e) for i, e in last_event.items() if not e["added"]]
    return {
        "available": any_activity,
        "added": added,
        "removed": removed,
        "net_change": len(added) - len(removed),
    }


def _transferred_items(cycle: Cycle, visible_issue_ids: set) -> List[Dict[str, Any]]:
    """Items moved out of a finished cycle (end-of-cycle transfer happens after end_date)."""
    moved = (
        IssueActivity.objects.filter(
            project_id=cycle.project_id,
            field="cycles",
            verb="updated",
            old_identifier=cycle.id,
            created_at__gt=cycle.end_date,
        )
        .values_list("issue_id", flat=True)
        .distinct()
    )
    ids = [i for i in moved if i in visible_issue_ids]
    return [_item_row(i) for i in _load_items(ids)[:INCOMPLETE_LIMIT]]


def build_cycle_report(user, slug: str, project_id, cycle: Cycle) -> Dict[str, Any]:
    if not cycle.start_date or not cycle.end_date:
        raise CycleWithoutDates()

    tz = _tz(cycle)
    now = timezone.now()
    today = now.astimezone(tz).date()
    start_day, end_day = _local_date(cycle.start_date, tz), _local_date(cycle.end_date, tz)
    days = [start_day + timedelta(days=n) for n in range((end_day - start_day).days + 1)]

    visible = scoped_issue_queryset(user, slug, [project_id])
    visible_issue_ids = set(visible.values_list("id", flat=True))
    in_cycle_ids = visible.filter(issue_cycle__cycle_id=cycle.id, issue_cycle__deleted_at__isnull=True).values("id")

    items = _load_items(in_cycle_ids)
    item_ids = [i["id"] for i in items]
    assignee_pairs = _relation_pairs(item_ids, "issue_assignee", "assignee_id", "assignee__display_name")
    label_pairs = _relation_pairs(item_ids, "label_issue", "label_id", "label__name", "label__color")
    for item in items:
        item["assignees"] = sorted(a["name"] for a in assignee_pairs.get(item["id"], []) if a["name"])

    status = "upcoming" if today < start_day else "completed" if today > end_day else "current"
    snapshot = cycle.progress_snapshot or {}
    source = "snapshot" if snapshot else "live"

    summary = _summary(items)
    burndown_issues = _burndown(items, days, today, tz, use_points=False)
    burndown_points = _burndown(items, days, today, tz, use_points=True) if summary["points"] else None
    assignees = _breakdown(items, assignee_pairs, "none")
    labels = _breakdown(items, label_pairs, "none")

    if snapshot:
        total = snapshot.get("total_issues", 0) or 0
        completed = snapshot.get("completed_issues", 0) or 0
        cancelled = snapshot.get("cancelled_issues", 0) or 0
        summary.update(
            {
                "total": total,
                "completed": completed,
                "cancelled": cancelled,
                "pending": total - completed - cancelled,
                "completion_pct": _pct(completed, total),
                "state_groups": {
                    "backlog": snapshot.get("backlog_issues", 0) or 0,
                    "unstarted": snapshot.get("unstarted_issues", 0) or 0,
                    "started": snapshot.get("started_issues", 0) or 0,
                    "completed": completed,
                    "cancelled": cancelled,
                },
            }
        )
        distribution = snapshot.get("distribution") or {}
        if distribution.get("completion_chart"):
            burndown_issues = distribution["completion_chart"]
        estimate_chart = (snapshot.get("estimate_distribution") or {}).get("completion_chart")
        burndown_points = estimate_chart or burndown_points
        assignees = _snapshot_breakdown(distribution.get("assignees"), "assignees") or assignees
        labels = _snapshot_breakdown(distribution.get("labels"), "labels") or labels

    priority_counts = {p: 0 for p in PRIORITIES}
    for item in items:
        priority_counts[item["priority"] if item["priority"] in priority_counts else "none"] += 1

    incomplete = [_item_row(i) for i in items if i["state__group"] not in CLOSED_GROUPS]
    transferred = _transferred_items(cycle, visible_issue_ids) if source == "snapshot" else []

    days_total = len(days)
    elapsed = 0 if today < start_day else min(days_total, (today - start_day).days + 1)
    if today > end_day:
        days_left = 0
    elif today < start_day:
        days_left = days_total
    else:
        days_left = (end_day - today).days

    return {
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "project_id": str(cycle.project_id),
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "timezone": str(tz),
            "status": status,
            "source": source,
        },
        "summary": {**summary, "days_total": days_total, "days_elapsed": elapsed, "days_left": days_left},
        "burndown": {"dates": [d.isoformat() for d in days], "issues": burndown_issues, "points": burndown_points},
        "breakdown": {
            "assignees": assignees,
            "labels": labels,
            "state_groups": [{"id": g, "name": g, "total": summary["state_groups"][g]} for g in STATE_GROUPS],
            "priorities": [{"id": p, "name": p, "total": priority_counts[p]} for p in PRIORITIES],
        },
        "scope_changes": _scope_changes(cycle, visible_issue_ids, now),
        "incomplete_items": {
            "results": incomplete[:INCOMPLETE_LIMIT],
            "total_count": len(incomplete),
            "truncated": len(incomplete) > INCOMPLETE_LIMIT,
        },
        "transferred_items": transferred,
        "meta": {"generated_at": now.isoformat(), "priorities_source": "live"},
    }
