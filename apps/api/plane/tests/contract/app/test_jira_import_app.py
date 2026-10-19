# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for importing Jira CSV exports."""

from pathlib import Path
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from plane.app.views.jira_import import base as views
from plane.db.models import JiraImport, Project, ProjectMember, User, WorkspaceMember

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "jira" / "jira_sample.csv"
URL = "/api/workspaces/{slug}/jira-imports/"


def _user(prefix):
    uid = uuid4().hex[:8]
    return User.objects.create(email=f"{prefix}-{uid}@sure.com.sa", username=f"{prefix}_{uid}")


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def queued(monkeypatch):
    """Keep files and Celery out of the request cycle; record what would be queued."""
    calls = {"run": [], "undo": [], "deleted": []}
    monkeypatch.setattr(views, "store_file", lambda key, content: True)
    monkeypatch.setattr(views, "delete_file", lambda key: calls["deleted"].append(key))
    monkeypatch.setattr(views.run_jira_import, "delay", lambda job_id: calls["run"].append(job_id))
    monkeypatch.setattr(views.undo_jira_import, "delay", lambda job_id: calls["undo"].append(job_id))
    return calls


@pytest.fixture
def env(db, workspace, create_user):
    web = Project.objects.create(name="Web", identifier="WEB", workspace=workspace)
    mobile = Project.objects.create(name="Mobile", identifier="MOB", workspace=workspace)

    lead = _user("lead")  # project admin of Web only
    WorkspaceMember.objects.create(workspace=workspace, member=lead, role=15)
    ProjectMember.objects.create(project=web, member=lead, workspace=workspace, role=20)
    ProjectMember.objects.create(project=mobile, member=lead, workspace=workspace, role=15)

    member = _user("member")  # no project admin role anywhere
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    ProjectMember.objects.create(project=web, member=member, workspace=workspace, role=15)

    guest = _user("guest")
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
    ProjectMember.objects.create(project=web, member=guest, workspace=workspace, role=20)

    return {"admin": create_user, "lead": lead, "member": member, "guest": guest, "web": web, "mobile": mobile}


def upload(client, slug, content=None, name="jira.csv"):
    data = content if content is not None else FIXTURE.read_bytes()
    file = SimpleUploadedFile(name, data, content_type="text/csv")
    return client.post(URL.format(slug=slug), {"file": file}, format="multipart")


@pytest.mark.contract
class TestJiraImportPermissions:
    def test_member_without_project_admin_role_is_rejected(self, workspace, env, queued):
        for who in ("member", "guest"):
            response = upload(_client(env[who]), workspace.slug)
            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert _client(env[who]).get(URL.format(slug=workspace.slug)).status_code == status.HTTP_403_FORBIDDEN

    def test_admin_upload_returns_analysis_and_options(self, workspace, env, queued):
        response = upload(_client(env["admin"]), workspace.slug)
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["status"] == "uploaded"
        assert response.data["analysis"]["work_item_count"] == 61
        options = response.data["options"]
        assert options["can_create_project"] is True
        assert options["suggested_identifier"] == {"identifier": "ALMS", "available": True}
        assert {p["identifier"] for p in options["projects"]} == {"WEB", "MOB"}

    def test_project_admin_sees_only_their_projects(self, workspace, env, queued):
        client = _client(env["lead"])
        response = upload(client, workspace.slug)
        assert response.status_code == status.HTTP_201_CREATED
        options = response.data["options"]
        assert options["can_create_project"] is False
        assert [p["identifier"] for p in options["projects"]] == ["WEB"]
        job_id = response.data["id"]
        start = URL.format(slug=workspace.slug) + f"{job_id}/start/"

        new = client.post(start, {"target": {"mode": "new", "name": "ALMS", "identifier": "ALMS"}}, format="json")
        assert new.status_code == status.HTTP_403_FORBIDDEN
        other = client.post(start, {"target": {"mode": "existing", "project_id": str(env["mobile"].id)}}, format="json")
        assert other.status_code == status.HTTP_403_FORBIDDEN
        assert queued["run"] == []

        ok = client.post(start, {"target": {"mode": "existing", "project_id": str(env["web"].id)}}, format="json")
        assert ok.status_code == status.HTTP_202_ACCEPTED, ok.data
        assert queued["run"] == [job_id]
        assert ok.data["status"] == "queued"

    def test_imports_are_private_to_their_initiator_unless_admin(self, workspace, env, queued):
        job_id = upload(_client(env["admin"]), workspace.slug).data["id"]
        lead = _client(env["lead"])
        assert lead.get(URL.format(slug=workspace.slug)).data == []
        assert lead.get(URL.format(slug=workspace.slug) + f"{job_id}/").status_code == status.HTTP_404_NOT_FOUND
        lead_job = upload(lead, workspace.slug).data["id"]
        listed = _client(env["admin"]).get(URL.format(slug=workspace.slug)).data
        assert {job["id"] for job in listed} == {job_id, lead_job}


@pytest.mark.contract
class TestJiraImportValidation:
    def test_rejects_bad_files(self, workspace, env, queued, settings):
        client = _client(env["admin"])
        assert upload(client, workspace.slug, b"a,b\n1,2\n").data["code"] == "missing_columns"
        assert upload(client, workspace.slug, name="jira.xlsx").data["code"] == "invalid_type"
        settings.FILE_SIZE_LIMIT = 10
        assert upload(client, workspace.slug).data["code"] == "file_too_large"
        assert JiraImport.objects.count() == 0

    def test_start_validates_target_and_mappings(self, workspace, env, queued):
        client = _client(env["admin"])
        job_id = upload(client, workspace.slug).data["id"]
        start = URL.format(slug=workspace.slug) + f"{job_id}/start/"

        taken = client.post(start, {"target": {"mode": "new", "name": "Alms", "identifier": "WEB"}}, format="json")
        assert taken.data["code"] == "identifier_taken"
        bad = client.post(start, {"target": {"mode": "new", "name": "Alms", "identifier": "A-B"}}, format="json")
        assert bad.data["code"] == "identifier_invalid"
        stranger = _user("stranger")
        wrong_member = client.post(
            start,
            {
                "target": {"mode": "new", "name": "Alms", "identifier": "ALMS"},
                "user_map": {"712020:00000000-0000-4000-8000-000000000001": str(stranger.id)},
            },
            format="json",
        )
        assert wrong_member.data["code"] == "invalid_member"
        assert queued["run"] == []

        ok = client.post(
            start,
            {
                "target": {"mode": "new", "name": "Alms", "identifier": "alms"},
                "priority_map": {"High": "low", "Medium": "bogus"},
                "options": {"comments": False},
            },
            format="json",
        )
        assert ok.status_code == status.HTTP_202_ACCEPTED, ok.data
        config = JiraImport.objects.get(pk=job_id).config
        assert config["target"] == {"mode": "new", "name": "Alms", "identifier": "ALMS", "jira_project": "ALMS"}
        assert config["priority_map"] == {"High": "low", "Medium": "none", "Highest": "urgent"}
        assert config["status_map"]["Done"] == {"mode": "create", "group": "completed"}
        assert config["options"]["comments"] is False and config["options"]["sprints_as_cycles"] is True

        again = client.post(start, {"target": {"mode": "new", "name": "Alms", "identifier": "ALMS"}}, format="json")
        assert again.status_code == status.HTTP_409_CONFLICT

    def test_undo_and_delete(self, workspace, env, queued):
        client = _client(env["admin"])
        job_id = upload(client, workspace.slug).data["id"]
        detail = URL.format(slug=workspace.slug) + f"{job_id}/"

        assert client.post(detail + "undo/").status_code == status.HTTP_409_CONFLICT
        JiraImport.objects.filter(pk=job_id).update(status="completed")
        undo = client.post(detail + "undo/")
        assert undo.status_code == status.HTTP_202_ACCEPTED
        assert queued["undo"] == [job_id]
        assert client.delete(detail).status_code == status.HTTP_409_CONFLICT

        JiraImport.objects.filter(pk=job_id).update(status="undone")
        assert client.delete(detail).status_code == status.HTTP_204_NO_CONTENT
        assert len(queued["deleted"]) == 1
        assert not JiraImport.objects.filter(pk=job_id).exists()
