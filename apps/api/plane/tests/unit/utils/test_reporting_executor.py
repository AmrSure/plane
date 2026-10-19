# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the report executor (plane.utils.reporting)."""

from datetime import datetime, timezone as dt_timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from plane.db.models import (
    Estimate,
    EstimatePoint,
    Issue,
    IssueAssignee,
    IssueLabel,
    Label,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)
from plane.utils.reporting import ReportQueryConfig, execute_chart, execute_number, execute_table
from plane.utils.reporting import executor as executor_module


def _user(prefix="user"):
    uid = uuid4().hex[:8]
    return User.objects.create(email=f"{prefix}-{uid}@sure.com.sa", username=f"{prefix}_{uid}")


def _project(workspace, owner, identifier, guest_view_all=False):
    project = Project.objects.create(
        name=f"Project {identifier}",
        identifier=identifier,
        workspace=workspace,
        guest_view_all_features=guest_view_all,
    )
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    return project


def _state(project, name, group):
    return State.objects.create(name=name, group=group, project=project, workspace=project.workspace, color="#000")


def _issue(project, author, state=None, **fields):
    issue = Issue(name=fields.pop("name", "Item"), project=project, workspace=project.workspace, state=state, **fields)
    issue.save(created_by_id=author.id)
    return issue


def _member(workspace, project, user, role=15, active=True):
    WorkspaceMember.objects.get_or_create(workspace=workspace, member=user, defaults={"role": role})
    return ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=role, is_active=active)


def _cfg(**kwargs):
    return ReportQueryConfig.from_payload(kwargs)


@pytest.fixture
def setup(db, workspace, create_user):
    owner = create_user
    project = _project(workspace, owner, "ALPHA")
    other = _project(workspace, owner, "BETA")
    todo = _state(project, "Todo", "unstarted")
    done = _state(project, "Done", "completed")
    _state(other, "Todo", "unstarted")
    items = [
        _issue(project, owner, todo, priority="high"),
        _issue(project, owner, todo, priority="low"),
        _issue(project, owner, done, priority="high"),
    ]
    _issue(other, owner, priority="urgent")
    return {"owner": owner, "project": project, "other": other, "todo": todo, "done": done, "items": items}


@pytest.mark.unit
@pytest.mark.django_db
class TestScope:
    def test_member_sees_all_projects(self, workspace, setup):
        result = execute_number(setup["owner"], workspace.slug, _cfg())
        assert result["value"] == 4
        assert result["meta"]["project_count"] == 2

    def test_non_member_sees_nothing_even_when_requesting_project(self, workspace, setup):
        outsider = _user("outsider")
        WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
        cfg = _cfg(project_ids=[str(setup["project"].id)])
        assert execute_number(outsider, workspace.slug, cfg)["value"] == 0

    def test_workspace_admin_without_project_membership_sees_nothing(self, workspace, setup):
        admin = _user("admin")
        WorkspaceMember.objects.create(workspace=workspace, member=admin, role=20)
        assert execute_number(admin, workspace.slug, _cfg())["value"] == 0

    def test_requested_projects_outside_scope_are_dropped(self, workspace, setup):
        member = _user("member")
        _member(workspace, setup["project"], member)
        cfg = _cfg(project_ids=[str(setup["project"].id), str(setup["other"].id)])
        assert execute_number(member, workspace.slug, cfg)["value"] == 3

    def test_restricted_guest_sees_only_own_items(self, workspace, setup):
        guest = _user("guest")
        _member(workspace, setup["project"], guest, role=5)
        _issue(setup["project"], guest, setup["todo"])
        assert execute_number(guest, workspace.slug, _cfg())["value"] == 1

    def test_guest_sees_all_when_project_allows(self, workspace, setup):
        setup["project"].guest_view_all_features = True
        setup["project"].save()
        guest = _user("guest")
        _member(workspace, setup["project"], guest, role=5)
        assert execute_number(guest, workspace.slug, _cfg())["value"] == 3

    def test_inactive_member_sees_nothing(self, workspace, setup):
        member = _user("inactive")
        _member(workspace, setup["project"], member, active=False)
        assert execute_number(member, workspace.slug, _cfg())["value"] == 0

    def test_archived_draft_and_deleted_items_are_excluded(self, workspace, setup):
        owner, project = setup["owner"], setup["project"]
        _issue(project, owner, setup["todo"], archived_at=timezone.now())
        _issue(project, owner, setup["todo"], is_draft=True)
        deleted = _issue(project, owner, setup["todo"])
        deleted.delete()
        assert execute_number(owner, workspace.slug, _cfg())["value"] == 4


@pytest.mark.unit
@pytest.mark.django_db
class TestMetrics:
    def _points(self, project, values, estimate_type="points"):
        estimate = Estimate.objects.create(name="E", type=estimate_type, project=project, workspace=project.workspace)
        return [
            EstimatePoint.objects.create(estimate=estimate, key=i, value=v, project=project, workspace=project.workspace)
            for i, v in enumerate(values)
        ]

    def test_points_sum_ignores_non_numeric_and_category_estimates(self, workspace, setup):
        owner, project, other = setup["owner"], setup["project"], setup["other"]
        three, xl = self._points(project, ["3", "XL"])
        (category,) = self._points(other, ["5"], estimate_type="categories")
        _issue(project, owner, setup["todo"], estimate_point=three)
        _issue(project, owner, setup["todo"], estimate_point=xl)
        _issue(other, owner, estimate_point=category)
        result = execute_number(owner, workspace.slug, _cfg(metric="ESTIMATE_POINT_COUNT"))
        assert result["value"] == 3.0

    def test_label_filter_does_not_double_count_points(self, workspace, setup):
        owner, project = setup["owner"], setup["project"]
        (five,) = self._points(project, ["5"])
        issue = _issue(project, owner, setup["todo"], estimate_point=five)
        bug = Label.objects.create(name="Bug", project=project, workspace=workspace)
        ui = Label.objects.create(name="UI", project=project, workspace=workspace)
        for label in (bug, ui):
            IssueLabel.objects.create(issue=issue, label=label, project=project, workspace=workspace)
        cfg = _cfg(metric="ESTIMATE_POINT_COUNT", filters={"label_id__in": [str(bug.id), str(ui.id)]})
        assert execute_number(owner, workspace.slug, cfg)["value"] == 5.0

    def test_multi_valued_group_by_counts_each_item_once_per_bucket(self, workspace, setup):
        owner, project = setup["owner"], setup["project"]
        a, b = _user("a"), _user("b")
        _member(workspace, project, a)
        _member(workspace, project, b)
        issue = setup["items"][0]
        for assignee in (a, b):
            IssueAssignee.objects.create(issue=issue, assignee=assignee, project=project, workspace=workspace)
        chart = execute_chart(owner, workspace.slug, _cfg(x_axis="STATE_GROUPS", group_by="ASSIGNEES"))
        unstarted = next(row for row in chart["data"] if row["key"] == "unstarted")
        # Three unstarted items (two in ALPHA, BETA's item takes its default Todo state).
        # The item with two assignees must be counted once in the bucket total, not twice.
        assert unstarted["count"] == 3
        assert unstarted[str(a.id)] == 1 and unstarted[str(b.id)] == 1
        assert unstarted["none"] == 2
        assert chart["totals"]["work_item_count"] == 4

    def test_soft_deleted_assignment_is_not_counted(self, workspace, setup):
        owner, project = setup["owner"], setup["project"]
        a = _user("a")
        _member(workspace, project, a)
        link = IssueAssignee.objects.create(issue=setup["items"][0], assignee=a, project=project, workspace=workspace)
        link.delete()
        chart = execute_chart(owner, workspace.slug, _cfg(x_axis="ASSIGNEES"))
        assert str(a.id) not in {row["key"] for row in chart["data"]}


@pytest.mark.unit
@pytest.mark.django_db
class TestChartShape:
    def test_priority_order_and_project_dimension(self, workspace, setup):
        owner = setup["owner"]
        chart = execute_chart(owner, workspace.slug, _cfg(x_axis="PRIORITY"))
        assert [row["key"] for row in chart["data"]] == ["urgent", "high", "low"]
        projects = execute_chart(owner, workspace.slug, _cfg(x_axis="PROJECTS"))
        counts = {row["name"]: row["count"] for row in projects["data"]}
        assert counts == {"Project ALPHA": 3, "Project BETA": 1}

    def test_month_grouping_uses_active_timezone(self, workspace, setup):
        owner, project = setup["owner"], setup["project"]
        issue = setup["items"][0]
        # 2026-01-31 23:30 UTC is already February 1st in Riyadh (UTC+3)
        Issue.all_objects.filter(id=issue.id).update(created_at=datetime(2026, 1, 31, 23, 30, tzinfo=dt_timezone.utc))
        cfg = _cfg(x_axis="CREATED_AT", date_grouping="MONTH", project_ids=[str(project.id)])
        with timezone.override(ZoneInfo("Asia/Riyadh")):
            chart = execute_chart(owner, workspace.slug, cfg)
        assert "2026-02-01" in {row["key"] for row in chart["data"]}

    def test_unknown_filter_field_is_rejected(self, workspace, setup):
        with pytest.raises(ValidationError):
            execute_number(setup["owner"], workspace.slug, _cfg(filters={"secret_field": "x"}))

    def test_group_by_must_differ_from_dimension(self):
        with pytest.raises(ValidationError):
            _cfg(x_axis="PRIORITY", group_by="PRIORITY")

    def test_category_buckets_are_truncated(self, workspace, setup, monkeypatch):
        monkeypatch.setattr(executor_module, "MAX_CATEGORY_BUCKETS", 2)
        chart = execute_chart(setup["owner"], workspace.slug, _cfg(x_axis="PRIORITY"))
        assert chart["meta"]["truncated"] is True
        assert chart["data"][-1]["key"] == "other"
        assert sum(row["count"] for row in chart["data"]) == 4

    def test_table_returns_requested_columns(self, workspace, setup):
        cfg = ReportQueryConfig.from_payload(
            {"table": {"columns": ["sequence_id", "name", "state_group", "assignees"], "limit": 2}},
            widget_type="table",
        )
        result = execute_table(setup["owner"], workspace.slug, cfg)
        assert result["total_count"] == 4
        assert len(result["results"]) == 2
        assert {"sequence_id", "name", "state_group", "assignees"} <= set(result["results"][0])
