# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Running, re-running and undoing Jira imports against the database."""

from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from plane.db.models import (
    Cycle,
    CycleIssue,
    EmailNotificationLog,
    Issue,
    IssueAssignee,
    IssueComment,
    IssueLabel,
    IssueLink,
    IssueRelation,
    JiraImport,
    Module,
    ModuleIssue,
    Notification,
    Project,
    ProjectIdentifier,
    State,
    User,
    WorkspaceMember,
)
from plane.utils.jira_import import runner
from plane.utils.jira_import.analyzer import analyze
from plane.utils.jira_import.reader import read_rows

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "jira"
TZ_NAME = "Asia/Riyadh"


def make_job(workspace, user, name, monkeypatch, **config):
    content = (FIXTURES / name).read_bytes()
    monkeypatch.setattr(runner, "load_file", lambda key: content)
    analysis = analyze(read_rows(content), [], ZoneInfo(TZ_NAME))
    config.setdefault("timezone", TZ_NAME)
    config.setdefault("priority_map", {p["name"]: p["suggested"] for p in analysis["priorities"]})
    config.setdefault(
        "status_map", {s["name"]: {"mode": "create", "group": s["suggested_group"]} for s in analysis["statuses"]}
    )
    return JiraImport.objects.create(
        workspace=workspace,
        initiated_by=user,
        file_key="test.csv",
        file_name=name,
        analysis=analysis,
        config=config,
        status=JiraImport.Status.QUEUED,
    )


def rerun(job, **config_changes):
    job.refresh_from_db()
    job.config = {**job.config, **config_changes, "resume_created": True}
    job.save()
    runner.run_import(job)
    job.refresh_from_db()
    return job


@pytest.fixture
def sam(db, workspace):
    user = User.objects.create(email=f"sam-{uuid4().hex[:6]}@sure.com.sa", username=f"sam{uuid4().hex[:6]}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    return user


@pytest.mark.django_db
class TestSampleImport:
    def run_sample(self, workspace, owner, sam, monkeypatch, **options):
        job = make_job(
            workspace,
            owner,
            "jira_sample.csv",
            monkeypatch,
            target={"mode": "new", "name": "ALMS", "identifier": "ALMS", "jira_project": "ALMS"},
            user_map={"712020:00000000-0000-4000-8000-000000000001": str(sam.id)},
            options=options,
        )
        runner.run_import(job)
        job.refresh_from_db()
        return job

    def test_creates_project_with_jira_keys(self, workspace, create_user, sam, monkeypatch):
        notifications = Notification.objects.count()
        emails = EmailNotificationLog.objects.count()
        job = self.run_sample(workspace, create_user, sam, monkeypatch)

        assert job.status == JiraImport.Status.COMPLETED, job.errors
        assert job.errors == []
        project = Project.objects.get(workspace=workspace, identifier="ALMS")
        assert job.project_id == project.id and job.created_project
        issues = Issue.objects.filter(project=project)
        assert issues.count() == 61
        assert job.summary["created"] == 61
        numbers = set(issues.values_list("sequence_id", flat=True))
        assert len(numbers) == 61 and min(numbers) == 2 and max(numbers) == 63
        task = issues.get(sequence_id=2)
        assert task.external_id and task.external_source == "jira"
        assert task.created_at.year == 2026

        # Done items are completed with their resolution time, the in-progress one is not
        done = issues.filter(state__name="Done")
        assert done.count() == 60
        assert not done.filter(completed_at__isnull=True).exists()
        assert issues.exclude(state__name="Done").get().completed_at is None
        assert issues.filter(priority="urgent").count() == 4

        # Sprints become cycles with sequential dates, each item in one cycle
        cycles = list(Cycle.objects.filter(project=project).order_by("start_date"))
        assert [c.name for c in cycles] == [f"ALMS Sprint {n}" for n in range(1, 6)]
        assert CycleIssue.objects.filter(issue__project=project).count() == 61

        # The mapped person is assigned, subscribed and a project member
        assert IssueAssignee.objects.filter(issue__project=project, assignee=sam).count() == 61
        assert project.project_projectmember.filter(member=sam).exists()
        assert IssueLabel.objects.filter(issue__project=project, label__name="Task").count() == 61

        # Importing is silent
        assert Notification.objects.count() == notifications
        assert EmailNotificationLog.objects.count() == emails

    def test_rerun_does_not_duplicate(self, workspace, create_user, sam, monkeypatch):
        job = self.run_sample(workspace, create_user, sam, monkeypatch)
        project = job.project
        Issue.objects.filter(project=project, sequence_id=2).update(name="Renamed here")

        job = rerun(job, target={"mode": "existing", "project_id": str(project.id), "jira_project": "ALMS"})
        assert job.status == JiraImport.Status.COMPLETED, job.errors
        assert Issue.objects.filter(project=project).count() == 61
        assert Cycle.objects.filter(project=project).count() == 5
        assert job.summary["updated"] == 61 and job.summary["created"] == 0
        assert Issue.objects.get(project=project, sequence_id=2).name != "Renamed here"

        job = rerun(job, options={"on_existing": "skip"})
        assert job.summary["skipped"] == 61

    def test_undo_removes_everything(self, workspace, create_user, sam, monkeypatch):
        job = self.run_sample(workspace, create_user, sam, monkeypatch)
        project_id = job.project_id
        runner.undo_import(job)

        assert not Project.objects.filter(pk=project_id).exists()
        assert not Issue.objects.filter(project_id=project_id).exists()
        assert not Cycle.objects.filter(project_id=project_id).exists()
        assert not ProjectIdentifier.objects.filter(workspace=workspace, name="ALMS").exists()

        # The identifier is free again, so the same file can be imported again
        job = make_job(
            workspace,
            create_user,
            "jira_sample.csv",
            monkeypatch,
            target={"mode": "new", "name": "ALMS", "identifier": "ALMS", "jira_project": "ALMS"},
            user_map={},
        )
        runner.run_import(job)
        job.refresh_from_db()
        assert job.status == JiraImport.Status.COMPLETED, job.errors
        assert Issue.objects.filter(project=job.project).count() == 61

    def test_renumbers_when_project_has_work_items(self, workspace, create_user, sam, monkeypatch):
        project = Project.objects.create(name="Existing", identifier="EXI", workspace=workspace)
        State.objects.create(name="Todo", group="unstarted", project=project, workspace=workspace, default=True)
        Issue(name="Already here", project=project, workspace=workspace).save(created_by_id=create_user.id)

        job = make_job(
            workspace,
            create_user,
            "jira_sample.csv",
            monkeypatch,
            target={"mode": "existing", "project_id": str(project.id), "jira_project": "ALMS"},
            user_map={},
        )
        runner.run_import(job)
        job.refresh_from_db()
        assert job.status == JiraImport.Status.COMPLETED, job.errors
        numbers = sorted(Issue.objects.filter(project=project).values_list("sequence_id", flat=True))
        assert numbers == list(range(1, 63))
        renumbered = Issue.objects.get(project=project, sequence_id=2)
        assert "Jira: ALMS-" in renumbered.description_html
        # Unmapped people are left unassigned and named on the item
        assert not IssueAssignee.objects.filter(issue__project=project).exists()
        assert "Assignee in Jira: Sam Rivera" in renumbered.description_html

        # Undo keeps the project and its own work item
        runner.undo_import(job)
        assert Project.objects.filter(pk=project.id).exists()
        assert list(Issue.objects.filter(project=project).values_list("name", flat=True)) == ["Already here"]


@pytest.mark.django_db
class TestRichImport:
    def test_epics_links_comments_and_attachments(self, workspace, create_user, monkeypatch):
        job = make_job(
            workspace,
            create_user,
            "jira_rich.csv",
            monkeypatch,
            target={"mode": "new", "name": "Demo", "identifier": "DEMO", "jira_project": "DEMO"},
            user_map={"aid-1": str(create_user.id), "aid-9": None},
        )
        runner.run_import(job)
        job.refresh_from_db()
        assert job.status == JiraImport.Status.COMPLETED, job.errors
        project = job.project

        # The epic becomes a module holding its child; it is not a work item
        assert Issue.objects.filter(project=project).count() == 3
        module = Module.objects.get(project=project)
        assert module.name == "Checkout revamp"
        story = Issue.objects.get(project=project, sequence_id=2)
        assert ModuleIssue.objects.filter(module=module, issue=story).exists()

        # Statuses, priorities, labels and story points
        assert story.state.name == "In Review" and story.state.group == "started"
        assert Issue.objects.get(project=project, sequence_id=4).state.group == "cancelled"
        assert story.priority == "high"
        assert set(IssueLabel.objects.filter(issue=story).values_list("label__name", flat=True)) == {
            "frontend",
            "ux",
            "Story",
        }
        assert story.estimate_point.value == "3"
        assert str(story.target_date) == "2026-03-20"

        # In two sprints: the item goes to the later cycle
        assert CycleIssue.objects.get(issue=story).cycle.name == "DEMO Sprint 2"

        # DEMO-3 blocks DEMO-2, DEMO-3 relates to DEMO-4
        bug = Issue.objects.get(project=project, sequence_id=3)
        assert IssueRelation.objects.filter(issue=story, related_issue=bug, relation_type="blocked_by").exists()
        assert IssueRelation.objects.filter(relation_type="relates_to", issue=bug).count() == 1

        # Comments keep their dates; an unmapped author is named in the text
        comments = list(IssueComment.objects.filter(issue=story).order_by("created_at"))
        assert len(comments) == 2
        assert comments[0].actor_id == create_user.id and "<strong>good</strong>" in comments[0].comment_html
        assert "Pat Unknown" in comments[1].comment_html
        assert comments[0].created_at.month == 3

        # Attachments are kept as links, markup is converted safely
        assert IssueLink.objects.get(issue=story).title == "mock.png"
        assert "<script" not in story.description_html and "<h2>Goal</h2>" in story.description_html
        assert "Reporter in Jira: Pat Unknown" in story.description_html

        # A bad date is ignored, not fatal
        assert bug.target_date is None

        # Re-running adds no comments, links or relations
        job = rerun(job, target={"mode": "existing", "project_id": str(project.id), "jira_project": "DEMO"})
        assert IssueComment.objects.filter(issue=story).count() == 2
        assert IssueLink.objects.filter(issue=story).count() == 1
        assert IssueRelation.objects.filter(issue__project=project).count() == 2
        assert Module.objects.filter(project=project).count() == 1
