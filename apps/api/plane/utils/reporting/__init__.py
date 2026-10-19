# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Report engine shared by workspace dashboards, saved reports and cycle reports.

Every number produced here is computed from a queryset scoped to the projects the
requesting user is an active member of (see scope.py). Nothing in this package
trusts the owner of a dashboard or report for data access.
"""

from .config import ReportQueryConfig, ReportQueryConfigSerializer
from .executor import QueryTimeout, execute_chart, execute_number, execute_table, to_export_rows
from .exporting import EXPORT_FORMATS, render_export
from .scope import get_project_scope, scoped_issue_queryset

__all__ = [
    "ReportQueryConfig",
    "ReportQueryConfigSerializer",
    "QueryTimeout",
    "execute_chart",
    "execute_number",
    "execute_table",
    "to_export_rows",
    "EXPORT_FORMATS",
    "render_export",
    "get_project_scope",
    "scoped_issue_queryset",
]
