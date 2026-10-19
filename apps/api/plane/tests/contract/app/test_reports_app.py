# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for workspace dashboards, saved reports and cycle reports."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Cycle,
    CycleIssue,
    Issue,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceDashboard,
    WorkspaceMember,
)

BASE = "/api/workspaces/{slug}"


def _user(prefix):
    uid = uuid4().hex[:8]
    return User.objects.create(email=f"{prefix}-{uid}@sure.com.sa", username=f"{prefix}_{uid}")


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def env(db, workspace, create_user):
    owner = create_user
    project = Project.objects.create(name="Web", identifier="WEB", workspace=workspace)
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    other_project = Project.objects.create(name="Mobile", identifier="MOB", workspace=workspace)
    ProjectMember.objects.create(project=other_project, member=owner, workspace=workspace, role=20)
    todo = State.objects.create(name="Todo", group="unstarted", project=project, workspace=workspace)
    done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
    State.objects.create(name="Todo", group="unstarted", project=other_project, workspace=workspace)

    def issue(proj, state=None, **kw):
        item = Issue(name=kw.pop("name", "Item"), project=proj, workspace=workspace, state=state, **kw)
        item.save(created_by_id=owner.id)
        return item

    items = [issue(project, todo), issue(project, done, completed_at=timezone.now()), issue(other_project)]

    member = _user("member")  # member of WEB only
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    ProjectMember.objects.create(project=project, member=member, workspace=workspace, role=15)

    admin = _user("admin")  # workspace admin, no project membership
    WorkspaceMember.objects.create(workspace=workspace, member=admin, role=20)

    guest = _user("guest")
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
    ProjectMember.objects.create(project=project, member=guest, workspace=workspace, role=5)

    return {
        "owner": owner,
        "member": member,
        "admin": admin,
        "guest": guest,
        "project": project,
        "other_project": other_project,
        "todo": todo,
        "done": done,
        "items": items,
        "issue": issue,
    }


def _create_dashboard(client, slug, access=0):
    response = client.post(f"{BASE.format(slug=slug)}/dashboards/", {"name": "Delivery", "access": access}, format="json")
    assert response.status_code == status.HTTP_201_CREATED, response.data
    return response.data


def _create_widget(client, slug, dashboard_id, **overrides):
    payload = {"name": "By state", "widget_type": "bar", "config": {"x_axis": "STATE_GROUPS"}, **overrides}
    response = client.post(f"{BASE.format(slug=slug)}/dashboards/{dashboard_id}/widgets/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED, response.data
    return response.data


@pytest.mark.contract
@pytest.mark.django_db
class TestDashboards:
    def test_owner_crud_and_visibility(self, workspace, env):
        owner_client = _client(env["owner"])
        dashboard = _create_dashboard(owner_client, workspace.slug)
        url = f"{BASE.format(slug=workspace.slug)}/dashboards/{dashboard['id']}/"

        # private: other members get 404, not 403
        member_client = _client(env["member"])
        assert member_client.get(url).status_code == status.HTTP_404_NOT_FOUND
        assert len(member_client.get(f"{BASE.format(slug=workspace.slug)}/dashboards/").data) == 0

        # shared: visible but not editable by others
        assert owner_client.patch(url, {"access": 1}, format="json").status_code == status.HTTP_200_OK
        assert member_client.get(url).status_code == status.HTTP_200_OK
        assert member_client.patch(url, {"name": "x"}, format="json").status_code == status.HTTP_403_FORBIDDEN
        assert member_client.delete(url).status_code == status.HTTP_403_FORBIDDEN

        # workspace admin may delete a shared dashboard
        assert _client(env["admin"]).delete(url).status_code == status.HTTP_204_NO_CONTENT
        assert not WorkspaceDashboard.objects.filter(id=dashboard["id"]).exists()

    def test_workspace_guest_is_rejected(self, workspace, env):
        response = _client(env["guest"]).get(f"{BASE.format(slug=workspace.slug)}/dashboards/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_widget_validation(self, workspace, env):
        client = _client(env["owner"])
        dashboard = _create_dashboard(client, workspace.slug)
        url = f"{BASE.format(slug=workspace.slug)}/dashboards/{dashboard['id']}/widgets/"
        bad = client.post(url, {"widget_type": "bar", "config": {}}, format="json")
        assert bad.status_code == status.HTTP_400_BAD_REQUEST
        pie = client.post(
            url, {"widget_type": "pie", "config": {"x_axis": "PRIORITY", "group_by": "LABELS"}}, format="json"
        )
        assert pie.status_code == status.HTTP_400_BAD_REQUEST

    def test_widget_data_is_scoped_to_viewer(self, workspace, env):
        owner_client = _client(env["owner"])
        dashboard = _create_dashboard(owner_client, workspace.slug, access=1)
        widget = _create_widget(owner_client, workspace.slug, dashboard["id"], widget_type="number", config={})
        url = f"{BASE.format(slug=workspace.slug)}/dashboards/{dashboard['id']}/widgets/{widget['id']}/data/"

        owner_data = owner_client.get(url)
        member_data = _client(env["member"]).get(url)
        assert owner_data.status_code == member_data.status_code == status.HTTP_200_OK
        assert owner_data.data["value"] == 3  # both projects
        assert member_data.data["value"] == 2  # WEB only

    def test_reorder_rejects_foreign_widgets(self, workspace, env):
        client = _client(env["owner"])
        first = _create_dashboard(client, workspace.slug)
        second = _create_dashboard(client, workspace.slug)
        own = _create_widget(client, workspace.slug, first["id"])
        foreign = _create_widget(client, workspace.slug, second["id"])
        url = f"{BASE.format(slug=workspace.slug)}/dashboards/{first['id']}/widgets/reorder/"

        ok = client.post(url, {"widgets": [{"id": own["id"], "sort_order": 5, "size": "full"}]}, format="json")
        assert ok.status_code == status.HTTP_200_OK
        assert ok.data[0]["size"] == "full"
        bad = client.post(url, {"widgets": [{"id": foreign["id"], "sort_order": 1}]}, format="json")
        assert bad.status_code == status.HTTP_400_BAD_REQUEST

    def test_preview(self, workspace, env):
        response = _client(env["owner"]).post(
            f"{BASE.format(slug=workspace.slug)}/dashboard-widgets/preview/",
            {"widget_type": "stacked_bar", "config": {"x_axis": "PROJECTS", "group_by": "STATE_GROUPS"}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["kind"] == "chart"
        assert response.data["totals"]["work_item_count"] == 3


@pytest.mark.contract
@pytest.mark.django_db
class TestReports:
    def test_saved_report_visibility(self, workspace, env):
        owner_client = _client(env["owner"])
        created = owner_client.post(
            f"{BASE.format(slug=workspace.slug)}/reports/",
            {"name": "Throughput", "config": {"x_axis": "PRIORITY"}, "display": {"chart_type": "bar"}},
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED, created.data
        url = f"{BASE.format(slug=workspace.slug)}/reports/{created.data['id']}/"
        assert _client(env["member"]).get(url).status_code == status.HTTP_404_NOT_FOUND
        assert owner_client.patch(url, {"access": 1}, format="json").status_code == status.HTTP_200_OK
        assert _client(env["member"]).get(url).status_code == status.HTTP_200_OK
        assert _client(env["member"]).patch(url, {"name": "x"}, format="json").status_code == 403

    def test_query_returns_chart_and_table(self, workspace, env):
        response = _client(env["member"]).post(
            f"{BASE.format(slug=workspace.slug)}/reports/query/",
            {"config": {"x_axis": "STATE_GROUPS"}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["chart"]["totals"]["work_item_count"] == 2
        assert response.data["table"]["total_count"] == 2

    @pytest.mark.parametrize("export_format,content_type", [("csv", "text/csv"), ("xlsx", "application/vnd")])
    def test_export(self, workspace, env, export_format, content_type):
        response = _client(env["owner"]).post(
            f"{BASE.format(slug=workspace.slug)}/reports/export/",
            {"format": export_format, "title": "Throughput", "config": {"x_axis": "PRIORITY"}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"].startswith(content_type)
        assert len(response.content) > 0


@pytest.mark.contract
@pytest.mark.django_db
class TestCycleReport:
    @pytest.fixture
    def cycle(self, workspace, env):
        now = timezone.now()
        cycle = Cycle.objects.create(
            name="Sprint 1",
            project=env["project"],
            workspace=workspace,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=5),
            owned_by=env["owner"],
        )
        for item in env["items"][:2]:
            CycleIssue.objects.create(issue=item, cycle=cycle, project=env["project"], workspace=workspace)
        return cycle

    def url(self, workspace, env, cycle, suffix=""):
        return f"{BASE.format(slug=workspace.slug)}/projects/{env['project'].id}/cycles/{cycle.id}/report/{suffix}"

    def test_member_gets_report(self, workspace, env, cycle):
        response = _client(env["member"]).get(self.url(workspace, env, cycle))
        assert response.status_code == status.HTTP_200_OK
        summary = response.data["summary"]
        assert (summary["total"], summary["completed"], summary["pending"]) == (2, 1, 1)
        assert summary["completion_pct"] == 50.0
        assert response.data["cycle"]["status"] == "current"
        assert len(response.data["burndown"]["dates"]) == 11

    def test_non_member_and_restricted_guest_are_rejected(self, workspace, env, cycle):
        outsider = _user("outsider")
        WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
        assert _client(outsider).get(self.url(workspace, env, cycle)).status_code == status.HTTP_403_FORBIDDEN
        guest_response = _client(env["guest"]).get(self.url(workspace, env, cycle))
        assert guest_response.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_allowed_when_project_permits(self, workspace, env, cycle):
        env["project"].guest_view_all_features = True
        env["project"].save()
        assert _client(env["guest"]).get(self.url(workspace, env, cycle)).status_code == status.HTTP_200_OK

    def test_cycle_without_dates(self, workspace, env):
        cycle = Cycle.objects.create(name="Draft", project=env["project"], workspace=workspace, owned_by=env["owner"])
        response = _client(env["owner"]).get(self.url(workspace, env, cycle))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "no_dates"

    def test_cycle_from_other_project_is_not_found(self, workspace, env, cycle):
        url = f"{BASE.format(slug=workspace.slug)}/projects/{env['other_project'].id}/cycles/{cycle.id}/report/"
        assert _client(env["owner"]).get(url).status_code == status.HTTP_404_NOT_FOUND

    def test_export_xlsx(self, workspace, env, cycle):
        response = _client(env["owner"]).post(
            self.url(workspace, env, cycle, "export/"), {"format": "xlsx"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"].startswith("application/vnd")
