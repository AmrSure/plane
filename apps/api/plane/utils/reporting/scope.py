# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which work items a user may see in reports.

Mirrors the rules used by the workspace views list
(plane.app.views.view.base.WorkspaceViewIssuesViewSet._get_project_permission_filters):
  * only projects where the user is an active member;
  * guests see every work item only when the project enables guest_view_all_features,
    otherwise only the work items they created.
Workspace admins get no extra access to projects they are not members of.
"""

from typing import Iterable, List, Optional, Tuple
from uuid import UUID

from django.db.models import Q, QuerySet

from plane.db.models import Issue, ProjectMember

GUEST_ROLE = 5


def get_project_scope(user, slug: str) -> Tuple[List[UUID], List[UUID]]:
    """Return (full_access_project_ids, created_by_only_project_ids) for the user."""
    rows = ProjectMember.objects.filter(
        workspace__slug=slug,
        member=user,
        is_active=True,
        project__archived_at__isnull=True,
        project__deleted_at__isnull=True,
    ).values_list("project_id", "role", "project__guest_view_all_features")

    full, limited = [], []
    for project_id, role, guest_view_all in rows:
        if role > GUEST_ROLE or guest_view_all:
            full.append(project_id)
        else:
            limited.append(project_id)
    return full, limited


def _restrict(ids: List[UUID], requested: Optional[set]) -> List[UUID]:
    if requested is None:
        return ids
    return [pid for pid in ids if str(pid) in requested]


def scoped_issue_queryset(user, slug: str, project_ids: Optional[Iterable] = None) -> QuerySet:
    """Work items the user may see, optionally narrowed to project_ids.

    Requested project ids outside the user's scope are silently dropped, so a
    shared configuration can never widen what a viewer sees.
    """
    full, limited = get_project_scope(user, slug)
    requested = {str(pid) for pid in project_ids} if project_ids else None
    full = _restrict(full, requested)
    limited = _restrict(limited, requested)

    if not full and not limited:
        return Issue.issue_objects.none()

    return Issue.issue_objects.filter(workspace__slug=slug).filter(
        Q(project_id__in=full) | Q(project_id__in=limited, created_by=user)
    )


def scoped_project_count(user, slug: str, project_ids: Optional[Iterable] = None) -> int:
    full, limited = get_project_scope(user, slug)
    requested = {str(pid) for pid in project_ids} if project_ids else None
    return len(_restrict(full, requested)) + len(_restrict(limited, requested))
