# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Cycle reports and their exports."""

from typing import Any, Dict, List

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Cycle, ProjectMember
from plane.utils.reporting import EXPORT_FORMATS, render_export
from plane.utils.reporting.cycle_report import CycleWithoutDates, build_cycle_report

from .common import forbidden, not_found

SECTIONS = (
    "summary",
    "burndown",
    "assignees",
    "labels",
    "state_groups",
    "priorities",
    "scope_changes",
    "incomplete_items",
)

DEFAULT_LABELS = {
    "metric": "Metric",
    "value": "Value",
    "date": "Date",
    "remaining_issues": "Remaining work items",
    "remaining_points": "Remaining points",
    "name": "Name",
    "total": "Total",
    "completed": "Completed",
    "pending": "Pending",
    "cancelled": "Cancelled",
    "completion_pct": "Completion %",
    "days_total": "Days",
    "days_left": "Days left",
    "points_total": "Points",
    "points_completed": "Points completed",
    "change": "Change",
    "added": "Added",
    "removed": "Removed",
    "id": "ID",
    "state": "State",
    "priority": "Priority",
    "assignees": "Assignees",
    "target_date": "Target date",
    "estimate": "Estimate",
}


def _guest_restricted(user, slug, project_id) -> bool:
    member = (
        ProjectMember.objects.filter(workspace__slug=slug, project_id=project_id, member=user, is_active=True)
        .values("role", "project__guest_view_all_features")
        .first()
    )
    return bool(member and member["role"] == ROLE.GUEST.value and not member["project__guest_view_all_features"])


def _load_report(request, slug, project_id, cycle_id):
    if _guest_restricted(request.user, slug, project_id):
        return None, forbidden("Guests cannot view cycle reports in this project.", code="guest_restricted")
    cycle = Cycle.objects.filter(workspace__slug=slug, project_id=project_id, pk=cycle_id).first()
    if not cycle:
        return None, not_found("Cycle not found")
    try:
        return build_cycle_report(request.user, slug, project_id, cycle), None
    except CycleWithoutDates:
        return None, Response(
            {"error": "This cycle has no start or end date.", "code": "no_dates"}, status=status.HTTP_400_BAD_REQUEST
        )


class CycleReportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, cycle_id):
        report, error = _load_report(request, slug, project_id, cycle_id)
        if error:
            return error
        return Response(report, status=status.HTTP_200_OK)


def _sheets(report: Dict[str, Any], labels: Dict[str, str], values: Dict[str, str], sheet_titles: Dict[str, str]):
    L = {**DEFAULT_LABELS, **{k: str(v) for k, v in labels.items() if isinstance(v, (str, int))}}

    def v(raw):
        return values.get(raw, raw) if isinstance(raw, str) else raw

    summary = report["summary"]
    summary_rows = [
        {L["metric"]: L[key], L["value"]: summary[key]}
        for key in ("total", "completed", "pending", "cancelled", "completion_pct", "days_total", "days_left")
    ]
    if summary.get("points"):
        summary_rows += [
            {L["metric"]: L["points_total"], L["value"]: summary["points"]["total"]},
            {L["metric"]: L["points_completed"], L["value"]: summary["points"]["completed"]},
        ]

    burndown = report["burndown"]
    burndown_rows = [
        {
            L["date"]: day,
            L["remaining_issues"]: (burndown["issues"] or {}).get(day),
            L["remaining_points"]: (burndown["points"] or {}).get(day) if burndown["points"] else None,
        }
        for day in burndown["dates"]
    ]

    def entity_rows(rows):
        return [
            {L["name"]: v(r["name"]), L["total"]: r["total"], L["completed"]: r["completed"], L["pending"]: r["pending"]}
            for r in rows
        ]

    def count_rows(rows):
        return [{L["name"]: v(r["name"]), L["total"]: r["total"]} for r in rows]

    def ident(item):
        return f"{item.get('project_identifier')}-{item.get('sequence_id')}" if item.get("sequence_id") else ""

    scope = report["scope_changes"]
    scope_rows = [
        {L["change"]: L[kind], L["id"]: ident(item), L["name"]: item["name"], L["date"]: item["at"][:10]}
        for kind in ("added", "removed")
        for item in scope[kind]
    ]

    item_rows = [
        {
            L["id"]: ident(item),
            L["name"]: item["name"],
            L["state"]: item["state_name"],
            L["priority"]: v(item["priority"]),
            L["assignees"]: item.get("assignees") or [],
            L["target_date"]: item["target_date"],
            L["estimate"]: item["estimate"],
        }
        for item in report["incomplete_items"]["results"]
    ]

    def title(key, fallback):
        return str(sheet_titles.get(key) or fallback)

    entity_headers = [L["name"], L["total"], L["completed"], L["pending"]]
    return {
        "summary": (title("summary", "Summary"), [L["metric"], L["value"]], summary_rows),
        "burndown": (
            title("burndown", "Burndown"),
            [L["date"], L["remaining_issues"], L["remaining_points"]],
            burndown_rows,
        ),
        "assignees": (title("assignees", "Assignees"), entity_headers, entity_rows(report["breakdown"]["assignees"])),
        "labels": (title("labels", "Labels"), entity_headers, entity_rows(report["breakdown"]["labels"])),
        "state_groups": (
            title("state_groups", "States"),
            [L["name"], L["total"]],
            count_rows(report["breakdown"]["state_groups"]),
        ),
        "priorities": (
            title("priorities", "Priorities"),
            [L["name"], L["total"]],
            count_rows(report["breakdown"]["priorities"]),
        ),
        "scope_changes": (
            title("scope_changes", "Scope changes"),
            [L["change"], L["id"], L["name"], L["date"]],
            scope_rows,
        ),
        "incomplete_items": (
            title("incomplete_items", "Incomplete items"),
            [L["id"], L["name"], L["state"], L["priority"], L["assignees"], L["target_date"], L["estimate"]],
            item_rows,
        ),
    }


class CycleReportExportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id, cycle_id):
        export_format = request.data.get("format", "xlsx")
        if export_format not in EXPORT_FORMATS:
            raise ValidationError({"format": "Use csv or xlsx."})
        section = request.data.get("section") or "summary"
        if section not in SECTIONS:
            raise ValidationError({"section": "Unknown section."})
        labels = request.data.get("labels") or {}
        if not isinstance(labels, dict):
            raise ValidationError({"labels": "Labels must be an object."})

        report, error = _load_report(request, slug, project_id, cycle_id)
        if error:
            return error

        sheets = _sheets(report, labels.get("columns") or {}, labels.get("values") or {}, labels.get("sheets") or {})
        ordered: List = [sheets[section]] if export_format == "csv" else [sheets[key] for key in SECTIONS]
        return render_export(export_format, report["cycle"]["name"], ordered)
