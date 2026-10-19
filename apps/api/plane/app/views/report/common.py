# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Helpers shared by dashboard, report and cycle report endpoints."""

from typing import Any, Dict, Optional

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.db.models import WorkspaceMember
from plane.utils.reporting import (
    QueryTimeout,
    ReportQueryConfig,
    execute_chart,
    execute_number,
    execute_table,
)

WORKSPACE_ADMIN = 20


def visible_q(user) -> Q:
    """Objects a user may open: their own, or anything shared with the workspace."""
    return Q(owned_by=user) | Q(access=1)


def is_workspace_admin(user, slug: str) -> bool:
    return WorkspaceMember.objects.filter(
        workspace__slug=slug, member=user, role=WORKSPACE_ADMIN, is_active=True
    ).exists()


def not_found(message: str = "Not found") -> Response:
    return Response({"error": message}, status=status.HTTP_404_NOT_FOUND)


def forbidden(message: str, code: Optional[str] = None) -> Response:
    body: Dict[str, Any] = {"error": message}
    if code:
        body["code"] = code
    return Response(body, status=status.HTTP_403_FORBIDDEN)


def timeout_response() -> Response:
    return Response(
        {"error": "The report took too long. Narrow the filters and try again.", "code": "query_timeout"},
        status=status.HTTP_400_BAD_REQUEST,
    )


def run_query(user, slug: str, widget_type: str, config: Dict[str, Any], overrides: Optional[Dict] = None):
    """Execute a widget/report config for the requesting user. Raises QueryTimeout."""
    cfg = ReportQueryConfig.from_payload(config, widget_type=widget_type)
    if widget_type == "number":
        return {"kind": "number", **execute_number(user, slug, cfg, overrides)}
    if widget_type == "table":
        return {"kind": "table", **execute_table(user, slug, cfg, overrides)}
    return {"kind": "chart", **execute_chart(user, slug, cfg, overrides)}


__all__ = [
    "QueryTimeout",
    "visible_q",
    "is_workspace_admin",
    "not_found",
    "forbidden",
    "timeout_response",
    "run_query",
]
