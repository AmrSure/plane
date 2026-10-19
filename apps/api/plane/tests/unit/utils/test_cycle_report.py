# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the cycle report builder."""

from datetime import timedelta

import pytest
from django.utils import timezone

from plane.db.models import Cycle, CycleIssue, Issue, IssueActivity, Project, ProjectMember, State
from plane.utils.reporting.cycle_report import CycleWithoutDates, build_cycle_report


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Web", identifier="WEB", workspace=workspace)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def states(project):
    return {
        group: State.objects.create(name=group.title(), group=group, project=project, workspace=project.workspace)
        for group in ("unstarted", "started", "completed", "cancelled")
    }


def _issue(project, author, state, **kw):
    item = Issue(name=kw.pop("name", "Item"), project=project, workspace=project.workspace, state=state, **kw)
    item.save(created_by_id=author.id)
    return item


def _cycle(project, start_offset=-3, end_offset=3, **kw):
    owner = ProjectMember.objects.filter(project=project, role=20).first().member
    now = timezone.now()
    return Cycle.objects.create(
        name="Sprint",
        project=project,
        workspace=project.workspace,
        start_date=now + timedelta(days=start_offset),
        end_date=now + timedelta(days=end_offset),
        owned_by=owner,
        **kw,
    )


def _link(cycle, issue):
    return CycleIssue.objects.create(issue=issue, cycle=cycle, project=cycle.project, workspace=cycle.workspace)


def _activity(cycle, issue, verb, at, old=None, new=None):
    activity = IssueActivity.objects.create(
        issue=issue,
        verb=verb,
        field="cycles",
        old_identifier=old,
        new_identifier=new,
        project=cycle.project,
        workspace=cycle.workspace,
    )
    IssueActivity.objects.filter(id=activity.id).update(created_at=at)
    return activity


@pytest.mark.unit
@pytest.mark.django_db
class TestCycleReport:
    def test_summary_and_burndown(self, workspace, create_user, project, states):
        cycle = _cycle(project)
        done = _issue(project, create_user, states["completed"], completed_at=timezone.now() - timedelta(days=1))
        _link(cycle, done)
        _link(cycle, _issue(project, create_user, states["started"]))
        _link(cycle, _issue(project, create_user, states["unstarted"]))
        _link(cycle, _issue(project, create_user, states["cancelled"]))

        report = build_cycle_report(create_user, workspace.slug, project.id, cycle)
        summary = report["summary"]
        assert (summary["total"], summary["completed"], summary["cancelled"], summary["pending"]) == (4, 1, 1, 2)
        assert summary["completion_pct"] == 25.0
        assert summary["days_total"] == 7 and summary["days_left"] == 3
        assert report["cycle"]["status"] == "current" and report["cycle"]["source"] == "live"

        burndown = report["burndown"]["issues"]
        dates = report["burndown"]["dates"]
        assert burndown[dates[0]] == 4  # nothing completed on the first day
        assert burndown[dates[-1]] is None  # future days are empty
        assert report["incomplete_items"]["total_count"] == 2

    def test_scope_changes_use_last_event_per_item(self, workspace, create_user, project, states):
        cycle = _cycle(project)
        added = _issue(project, create_user, states["unstarted"], name="Added")
        flip = _issue(project, create_user, states["unstarted"], name="Added then removed")
        early = _issue(project, create_user, states["unstarted"], name="Before start")
        _link(cycle, added)
        _link(cycle, early)
        now = timezone.now()
        _activity(cycle, added, "created", now - timedelta(days=1), new=cycle.id)
        _activity(cycle, flip, "created", now - timedelta(days=2), new=cycle.id)
        _activity(cycle, flip, "deleted", now - timedelta(days=1), old=cycle.id)
        _activity(cycle, early, "created", cycle.start_date - timedelta(days=1), new=cycle.id)

        scope = build_cycle_report(create_user, workspace.slug, project.id, cycle)["scope_changes"]
        assert scope["available"] is True
        assert [i["name"] for i in scope["added"]] == ["Added"]
        assert [i["name"] for i in scope["removed"]] == ["Added then removed"]
        assert scope["net_change"] == 0

    def test_scope_unavailable_without_activity(self, workspace, create_user, project, states):
        cycle = _cycle(project)
        _link(cycle, _issue(project, create_user, states["unstarted"]))
        assert build_cycle_report(create_user, workspace.slug, project.id, cycle)["scope_changes"]["available"] is False

    def test_snapshot_source(self, workspace, create_user, project, states):
        cycle = _cycle(
            project,
            start_offset=-10,
            end_offset=-2,
            progress_snapshot={
                "total_issues": 10,
                "completed_issues": 6,
                "cancelled_issues": 1,
                "started_issues": 2,
                "unstarted_issues": 1,
                "backlog_issues": 0,
                "distribution": {"assignees": [], "labels": [], "completion_chart": {"2026-01-01": 4}},
            },
        )
        report = build_cycle_report(create_user, workspace.slug, project.id, cycle)
        assert report["cycle"]["source"] == "snapshot" and report["cycle"]["status"] == "completed"
        assert report["summary"]["total"] == 10 and report["summary"]["completion_pct"] == 60.0
        assert report["summary"]["days_left"] == 0

    def test_cycle_without_dates(self, workspace, create_user, project):
        cycle = Cycle.objects.create(name="Draft", project=project, workspace=workspace, owned_by=create_user)
        with pytest.raises(CycleWithoutDates):
            build_cycle_report(create_user, workspace.slug, project.id, cycle)
