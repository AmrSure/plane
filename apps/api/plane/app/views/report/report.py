# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Saved custom reports, ad-hoc report queries and exports."""

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.report import SavedReportSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import SavedReport, Workspace
from plane.utils.reporting import (
    EXPORT_FORMATS,
    ReportQueryConfig,
    execute_chart,
    execute_number,
    execute_table,
    render_export,
    to_export_rows,
)
from plane.utils.reporting.config import DEFAULT_TABLE_COLUMNS, TABLE_COLUMNS

from .common import QueryTimeout, forbidden, is_workspace_admin, not_found, timeout_response, visible_q

EXPORT_ITEM_LIMIT = 5000


def _visible_reports(request, slug):
    return SavedReport.objects.filter(workspace__slug=slug).filter(visible_q(request.user))


class SavedReportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug, pk=None):
        if pk:
            report = _visible_reports(request, slug).filter(pk=pk).first()
            if not report:
                return not_found("Report not found")
            return Response(SavedReportSerializer(report, context={"request": request}).data)
        reports = _visible_reports(request, slug)
        search = request.GET.get("search")
        if search:
            reports = reports.filter(name__icontains=search)
        return Response(SavedReportSerializer(reports, many=True, context={"request": request}).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = SavedReportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save(workspace=workspace, owned_by=request.user)
        return Response(SavedReportSerializer(report, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, pk):
        report = _visible_reports(request, slug).filter(pk=pk).first()
        if not report:
            return not_found("Report not found")
        if report.owned_by_id != request.user.id:
            return forbidden("Only the owner can edit this report.")
        serializer = SavedReportSerializer(report, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, pk):
        report = _visible_reports(request, slug).filter(pk=pk).first()
        if not report:
            return not_found("Report not found")
        if report.owned_by_id != request.user.id and not is_workspace_admin(request.user, slug):
            return forbidden("Only the owner or a workspace admin can delete this report.")
        report.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportQueryEndpoint(BaseAPIView):
    """Run a report config: chart (when a dimension is set), number totals and a work item table."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        config = dict(request.data.get("config") or {})
        include_table = bool(request.data.get("include_table", True))
        try:
            cfg = ReportQueryConfig.from_payload(config)
            response = {}
            if cfg.x_axis:
                response["chart"] = execute_chart(request.user, slug, cfg)
            else:
                response["number"] = execute_number(request.user, slug, cfg)
            if include_table:
                table_cfg = ReportQueryConfig.from_payload(
                    {**config, "table": config.get("table") or {"columns": DEFAULT_TABLE_COLUMNS, "limit": 50}},
                    widget_type="table",
                )
                response["table"] = execute_table(request.user, slug, table_cfg)
        except QueryTimeout:
            return timeout_response()
        return Response(response, status=status.HTTP_200_OK)


class ReportExportEndpoint(BaseAPIView):
    """Export a report as CSV (chart pivot or work items) or XLSX (both, one sheet each)."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        export_format = request.data.get("format", "csv")
        if export_format not in EXPORT_FORMATS:
            raise ValidationError({"format": "Use csv or xlsx."})
        config = dict(request.data.get("config") or {})
        title = str(request.data.get("title") or "report")[:120]
        labels = request.data.get("labels") or {}
        if not isinstance(labels, dict):
            raise ValidationError({"labels": "Labels must be an object."})
        value_labels = labels.get("values") or {}
        column_labels = labels.get("columns") or {}
        sheet_labels = labels.get("sheets") or {}

        try:
            cfg = ReportQueryConfig.from_payload(config)
            sheets = []
            if cfg.x_axis:
                chart = execute_chart(request.user, slug, cfg)
                headers, rows = to_export_rows(
                    chart,
                    str(labels.get("dimension") or cfg.x_axis),
                    str(labels.get("total") or "Total"),
                    value_labels,
                )
                sheets.append((str(sheet_labels.get("summary") or "Summary"), headers, rows))
            if export_format == "xlsx" or not cfg.x_axis:
                columns = [c for c in (config.get("table") or {}).get("columns") or TABLE_COLUMNS if c in TABLE_COLUMNS]
                table_cfg = ReportQueryConfig.from_payload(
                    {**config, "table": {"columns": columns, "limit": 1, "order_by": "-created_at"}}, widget_type="table"
                )
                table = execute_table(request.user, slug, table_cfg, limit=EXPORT_ITEM_LIMIT)
                headers = [str(column_labels.get(c) or c) for c in columns]
                rows = []
                for item in table["results"]:
                    row = {}
                    for column, header in zip(columns, headers):
                        value = item.get(column)
                        if column in ("priority", "state_group") and value in value_labels:
                            value = value_labels[value]
                        row[header] = value
                    rows.append(row)
                sheets.append((str(sheet_labels.get("items") or "Work items"), headers, rows))
        except QueryTimeout:
            return timeout_response()
        return render_export(export_format, title, sheets)
