# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace dashboards and their widgets."""

from django.db import transaction
from django.db.models import Count, Max, Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.report import WorkspaceDashboardSerializer, WorkspaceDashboardWidgetSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace, WorkspaceDashboard, WorkspaceDashboardWidget

from .common import QueryTimeout, forbidden, is_workspace_admin, not_found, run_query, timeout_response, visible_q

WIDGET_GAP = 10000


def _visible_dashboards(request, slug):
    return WorkspaceDashboard.objects.filter(workspace__slug=slug).filter(visible_q(request.user))


def _get_visible_dashboard(request, slug, pk):
    return _visible_dashboards(request, slug).filter(pk=pk).first()


class WorkspaceDashboardEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug, pk=None):
        if pk:
            dashboard = _get_visible_dashboard(request, slug, pk)
            if not dashboard:
                return not_found("Dashboard not found")
            data = WorkspaceDashboardSerializer(dashboard, context={"request": request}).data
            data["widgets"] = WorkspaceDashboardWidgetSerializer(
                dashboard.widgets.filter(deleted_at__isnull=True).order_by("sort_order", "created_at"), many=True
            ).data
            return Response(data, status=status.HTTP_200_OK)

        dashboards = _visible_dashboards(request, slug).annotate(
            widget_count=Count("widgets", filter=Q(widgets__deleted_at__isnull=True))
        )
        search = request.GET.get("search")
        if search:
            dashboards = dashboards.filter(name__icontains=search)
        serializer = WorkspaceDashboardSerializer(dashboards, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = WorkspaceDashboardSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        dashboard = serializer.save(workspace=workspace, owned_by=request.user)
        return Response(
            WorkspaceDashboardSerializer(dashboard, context={"request": request}).data, status=status.HTTP_201_CREATED
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, pk):
        dashboard = _get_visible_dashboard(request, slug, pk)
        if not dashboard:
            return not_found("Dashboard not found")
        if dashboard.owned_by_id != request.user.id:
            return forbidden("Only the owner can edit this dashboard.")
        serializer = WorkspaceDashboardSerializer(dashboard, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, pk):
        dashboard = _get_visible_dashboard(request, slug, pk)
        if not dashboard:
            return not_found("Dashboard not found")
        if dashboard.owned_by_id != request.user.id and not is_workspace_admin(request.user, slug):
            return forbidden("Only the owner or a workspace admin can delete this dashboard.")
        with transaction.atomic():
            WorkspaceDashboardWidget.objects.filter(dashboard=dashboard).delete()
            dashboard.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceDashboardWidgetEndpoint(BaseAPIView):
    def _owned_dashboard(self, request, slug, dashboard_id):
        dashboard = _get_visible_dashboard(request, slug, dashboard_id)
        if not dashboard:
            return None, not_found("Dashboard not found")
        if dashboard.owned_by_id != request.user.id:
            return None, forbidden("Only the owner can change widgets on this dashboard.")
        return dashboard, None

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug, dashboard_id):
        dashboard = _get_visible_dashboard(request, slug, dashboard_id)
        if not dashboard:
            return not_found("Dashboard not found")
        widgets = dashboard.widgets.filter(deleted_at__isnull=True).order_by("sort_order", "created_at")
        return Response(WorkspaceDashboardWidgetSerializer(widgets, many=True).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, dashboard_id):
        dashboard, error = self._owned_dashboard(request, slug, dashboard_id)
        if error:
            return error
        serializer = WorkspaceDashboardWidgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        last = dashboard.widgets.filter(deleted_at__isnull=True).aggregate(m=Max("sort_order"))["m"]
        sort_order = serializer.validated_data.get("sort_order") or ((last or 0) + WIDGET_GAP)
        widget = serializer.save(dashboard=dashboard, workspace_id=dashboard.workspace_id, sort_order=sort_order)
        return Response(WorkspaceDashboardWidgetSerializer(widget).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, dashboard_id, pk):
        dashboard, error = self._owned_dashboard(request, slug, dashboard_id)
        if error:
            return error
        widget = dashboard.widgets.filter(pk=pk, deleted_at__isnull=True).first()
        if not widget:
            return not_found("Widget not found")
        serializer = WorkspaceDashboardWidgetSerializer(widget, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, dashboard_id, pk):
        dashboard, error = self._owned_dashboard(request, slug, dashboard_id)
        if error:
            return error
        widget = dashboard.widgets.filter(pk=pk, deleted_at__isnull=True).first()
        if not widget:
            return not_found("Widget not found")
        widget.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceDashboardWidgetReorderEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, dashboard_id):
        dashboard = _get_visible_dashboard(request, slug, dashboard_id)
        if not dashboard:
            return not_found("Dashboard not found")
        if dashboard.owned_by_id != request.user.id:
            return forbidden("Only the owner can change the layout of this dashboard.")

        items = request.data.get("widgets")
        if not isinstance(items, list) or not items:
            raise ValidationError({"widgets": "A list of widgets is required."})

        widgets = {str(w.id): w for w in dashboard.widgets.filter(deleted_at__isnull=True)}
        sizes = {choice for choice, _ in WorkspaceDashboardWidget.WidgetSize.choices}
        updated = []
        for item in items:
            widget = widgets.get(str(item.get("id")))
            if widget is None:
                raise ValidationError({"widgets": "Every widget must belong to this dashboard."})
            if "sort_order" in item:
                try:
                    widget.sort_order = float(item["sort_order"])
                except (TypeError, ValueError):
                    raise ValidationError({"widgets": "sort_order must be a number."})
            if "size" in item:
                if item["size"] not in sizes:
                    raise ValidationError({"widgets": "Invalid widget size."})
                widget.size = item["size"]
            updated.append(widget)

        WorkspaceDashboardWidget.objects.bulk_update(updated, ["sort_order", "size"], batch_size=100)
        ordered = dashboard.widgets.filter(deleted_at__isnull=True).order_by("sort_order", "created_at")
        return Response(WorkspaceDashboardWidgetSerializer(ordered, many=True).data, status=status.HTTP_200_OK)


class WorkspaceDashboardWidgetDataEndpoint(BaseAPIView):
    """Widget results, always computed with the viewer's own project access."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug, dashboard_id, pk):
        dashboard = _get_visible_dashboard(request, slug, dashboard_id)
        if not dashboard:
            return not_found("Dashboard not found")
        widget = dashboard.widgets.filter(pk=pk, deleted_at__isnull=True).first()
        if not widget:
            return not_found("Widget not found")
        try:
            result = run_query(request.user, slug, widget.widget_type, widget.config, overrides=dashboard.filters)
        except QueryTimeout:
            return timeout_response()
        return Response(result, status=status.HTTP_200_OK)


class WorkspaceDashboardWidgetPreviewEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        widget_type = request.data.get("widget_type")
        if widget_type not in {choice for choice, _ in WorkspaceDashboardWidget.WidgetType.choices}:
            raise ValidationError({"widget_type": "Invalid widget type."})
        try:
            result = run_query(request.user, slug, widget_type, request.data.get("config") or {})
        except QueryTimeout:
            return timeout_response()
        return Response(result, status=status.HTTP_200_OK)
