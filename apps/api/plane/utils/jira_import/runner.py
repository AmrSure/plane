# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Run (and undo) a Jira CSV import.

Everything is written through the ORM directly. No view code, activity task, webhook or
notification task is involved, so importing never notifies or emails anyone.
Each work item is written in its own savepoint: a bad row is recorded and skipped.
"""

import html
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from plane.db.models import (
    Cycle,
    CycleIssue,
    Estimate,
    EstimatePoint,
    Issue,
    IssueActivity,
    IssueAssignee,
    IssueComment,
    IssueLabel,
    IssueLink,
    IssueRelation,
    IssueSequence,
    IssueSubscriber,
    JiraImport,
    Label,
    Module,
    ModuleIssue,
    Project,
    ProjectIdentifier,
    ProjectMember,
    State,
    WorkspaceMember,
)
from plane.db.models.state import DEFAULT_STATES

from .analyzer import (
    EPIC_LINK_COLUMNS,
    LINK_PREFIXES,
    STORY_POINT_COLUMNS,
    attachment_parts,
    comment_parts,
    is_epic,
    order_sprints,
)
from .dates import parse_date, parse_datetime, safe_zone
from .markup import jira_to_html
from .reader import Row, first, issue_number, project_key, read_rows
from .storage import load_file

SOURCE = "jira"
MAX_ERRORS = 500
PROGRESS_EVERY = 25
ADMIN, MEMBER = 20, 15

GROUP_COLORS = {state["group"]: state["color"] for state in DEFAULT_STATES}
MODULE_STATUS = {"completed": "completed", "started": "in-progress", "cancelled": "cancelled", "backlog": "backlog"}

LABEL_COLORS = ("#3E63DD", "#30A46C", "#F76B15", "#E5484D", "#8E4EC6", "#12A594", "#D6409F", "#FFC53D")

DEFAULT_OPTIONS = {
    "keep_keys": True,
    "sprints_as_cycles": True,
    "epics_as_modules": True,
    "issue_types_as_labels": True,
    "comments": True,
    "attachments": True,
    "watchers": True,
    "on_existing": "update",
}


def _blank_created() -> Dict[str, List[str]]:
    return {
        key: []
        for key in (
            "projects",
            "project_members",
            "states",
            "labels",
            "estimates",
            "estimate_points",
            "cycles",
            "modules",
            "issues",
            "comments",
            "links",
        )
    }


class ImportRun:
    def __init__(self, job: JiraImport):
        self.job = job
        self.config: Dict[str, Any] = job.config or {}
        self.options: Dict[str, Any] = {**DEFAULT_OPTIONS, **(self.config.get("options") or {})}
        self.workspace = job.workspace
        self.initiator_id = job.initiated_by_id
        self.tz = safe_zone(self.config.get("timezone"))
        self.user_map: Dict[str, Optional[str]] = self.config.get("user_map") or {}
        self.priority_map: Dict[str, str] = self.config.get("priority_map") or {}
        self.status_map: Dict[str, Dict[str, Any]] = self.config.get("status_map") or {}
        self.created = _blank_created()
        if self.config.get("resume_created"):
            for key, ids in (job.created_ids or {}).items():
                self.created.setdefault(key, []).extend(ids)
        self.summary: Dict[str, int] = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "cycles": 0,
            "modules": 0,
            "labels": 0,
            "states": 0,
            "comments": 0,
            "links": 0,
            "relations": 0,
        }
        self.errors: List[Dict[str, Any]] = []
        self.project: Optional[Project] = None
        self.states: Dict[str, State] = {}
        self.labels: Dict[str, Label] = {}
        self.cycles: Dict[str, Cycle] = {}
        self.modules: Dict[str, Module] = {}
        self.points: Dict[str, EstimatePoint] = {}
        self.sprint_order: Dict[str, int] = {}
        self.account_names: Dict[str, str] = {}
        self.issue_by_id: Dict[str, Issue] = {}
        self.issue_by_key: Dict[str, Issue] = {}
        self.new_issue_ids: set = set()
        self.keep_keys = bool(self.options["keep_keys"])

    # ------------------------------------------------------------------ helpers

    def member(self, account_id: str, name: str = "") -> Optional[str]:
        key = account_id or (f"name:{name.strip().lower()}" if name else "")
        return self.user_map.get(key) if key else None

    def people(self, row: Row, name_col: str, id_col: str) -> set:
        names, ids = row.get(name_col, []), row.get(id_col, [])
        found = set()
        for index in range(max(len(names), len(ids))):
            member_id = self.member(ids[index] if index < len(ids) else "", names[index] if index < len(names) else "")
            if member_id:
                found.add(member_id)
        return found

    def error(self, row_index: int, key: str, exc: Exception) -> None:
        self.summary["failed"] += 1
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"row": row_index + 2, "key": key, "message": str(exc)[:300]})

    def save_progress(self, processed: int) -> None:
        JiraImport.objects.filter(pk=self.job.pk).update(processed=processed)

    def when(self, value: str) -> Optional[datetime]:
        return parse_datetime(value, self.tz)

    # ------------------------------------------------------------------ project

    def prepare_project(self) -> None:
        target = self.config.get("target") or {}
        if target.get("mode") == "new":
            identifier = (target.get("identifier") or "").strip().upper()
            project = Project(
                name=(target.get("name") or identifier)[:255],
                identifier=identifier,
                workspace=self.workspace,
                network=2,
                cycle_view=True,
                module_view=True,
                timezone=self.config.get("timezone") or self.workspace.timezone,
                external_source=SOURCE,
                external_id=target.get("jira_project") or identifier,
            )
            project.save(created_by_id=self.initiator_id)
            ProjectIdentifier.objects.create(name=identifier, project=project, workspace=self.workspace)
            ProjectMember.objects.create(project=project, member_id=self.initiator_id, role=ADMIN)
            State.objects.bulk_create(
                [
                    State(
                        name=state["name"],
                        color=state["color"],
                        project=project,
                        workspace=self.workspace,
                        sequence=state["sequence"],
                        group=state["group"],
                        default=state.get("default", False),
                        created_by_id=self.initiator_id,
                    )
                    for state in DEFAULT_STATES
                ]
            )
            self.created["projects"].append(str(project.id))
            self.job.created_project = True
        else:
            project = Project.objects.get(pk=target.get("project_id"), workspace=self.workspace)
            if not project.cycle_view or not project.module_view:
                Project.objects.filter(pk=project.pk).update(cycle_view=True, module_view=True)
        self.project = project
        self.job.project = project
        if self.keep_keys:
            self.keep_keys = can_keep_keys(project)

        # Mapped people must be project members to be assigned
        member_ids = {m for m in self.user_map.values() if m}
        active = set(
            WorkspaceMember.objects.filter(
                workspace=self.workspace, member_id__in=member_ids, is_active=True
            ).values_list("member_id", flat=True)
        )
        existing = set(
            str(m)
            for m in ProjectMember.objects.filter(project=project, member_id__in=member_ids).values_list(
                "member_id", flat=True
            )
        )
        for member_id in active:
            if str(member_id) not in existing:
                pm = ProjectMember.objects.create(project=project, member_id=member_id, role=MEMBER)
                self.created["project_members"].append(str(pm.id))
        # Unmapped or inactive people are treated as unmapped
        self.user_map = {k: (v if v and v in {str(a) for a in active} else None) for k, v in self.user_map.items()}

    # ------------------------------------------------------------------ reference data

    def prepare_states(self, rows: List[Row]) -> None:
        existing = {s.name.lower(): s for s in State.objects.filter(project=self.project)}
        for status in sorted({first(r, "Status") for r in rows if first(r, "Status")}):
            choice = self.status_map.get(status) or {"mode": "create", "group": "unstarted"}
            if choice.get("mode") == "existing" and choice.get("state_id"):
                state = State.objects.filter(project=self.project, pk=choice["state_id"]).first()
                if state:
                    self.states[status] = state
                    continue
            group = choice.get("group") or "unstarted"
            state = existing.get(status.lower())
            if state is None:
                state = State(
                    name=status[:255],
                    group=group,
                    color=GROUP_COLORS.get(group, "#60646C"),
                    project=self.project,
                    workspace=self.workspace,
                    external_source=SOURCE,
                    external_id=status[:255],
                )
                state.save(created_by_id=self.initiator_id)
                existing[status.lower()] = state
                self.created["states"].append(str(state.id))
                self.summary["states"] += 1
            self.states[status] = state

    def label(self, name: str) -> Label:
        key = name.strip()[:255]
        if key.lower() not in self.labels:
            label = Label.objects.filter(project=self.project, name__iexact=key).first()
            if label is None:
                label = Label(
                    name=key,
                    color=LABEL_COLORS[len(self.created["labels"]) % len(LABEL_COLORS)],
                    project=self.project,
                    workspace=self.workspace,
                    external_source=SOURCE,
                )
                label.save(created_by_id=self.initiator_id)
                self.created["labels"].append(str(label.id))
                self.summary["labels"] += 1
            self.labels[key.lower()] = label
        return self.labels[key.lower()]

    def prepare_estimates(self, rows: List[Row]) -> None:
        values = set()
        for row in rows:
            raw = next((first(row, c) for c in STORY_POINT_COLUMNS if first(row, c)), "")
            if raw:
                try:
                    number = Decimal(raw)
                    values.add(format(number.normalize(), "f"))
                except InvalidOperation:
                    continue
        if not values:
            return
        estimate = self.project.estimate
        if estimate is not None and estimate.type != "points":
            return  # the project measures with categories; story points are not mapped
        if estimate is None:
            estimate = Estimate(name="Story points", type="points", project=self.project, workspace=self.workspace)
            estimate.save(created_by_id=self.initiator_id)
            Project.objects.filter(pk=self.project.pk).update(estimate=estimate)
            self.created["estimates"].append(str(estimate.id))
        points = {p.value: p for p in EstimatePoint.objects.filter(estimate=estimate)}
        next_key = max([p.key for p in points.values()] + [-1]) + 1
        for value in sorted(values, key=lambda v: Decimal(v)):
            if value not in points:
                point = EstimatePoint(
                    estimate=estimate, key=next_key, value=value, project=self.project, workspace=self.workspace
                )
                point.save(created_by_id=self.initiator_id)
                points[value] = point
                next_key += 1
                self.created["estimate_points"].append(str(point.id))
        self.points = points

    def prepare_cycles(self) -> None:
        if not self.options["sprints_as_cycles"]:
            return
        sprints = order_sprints(list((self.job.analysis or {}).get("sprints") or []))
        for sprint in sprints:
            name = sprint["name"][:255]
            cycle = Cycle.objects.filter(project=self.project, external_source=SOURCE, external_id=name).first()
            if cycle is None:
                start = datetime.fromisoformat(sprint["start"]) if sprint.get("start") else None
                end = datetime.fromisoformat(sprint["end"]) if sprint.get("end") else None
                cycle = Cycle(
                    name=name,
                    project=self.project,
                    workspace=self.workspace,
                    start_date=start,
                    end_date=end,
                    owned_by_id=self.initiator_id,
                    timezone=self.project.timezone,
                    external_source=SOURCE,
                    external_id=name,
                )
                cycle.save(created_by_id=self.initiator_id)
                self.created["cycles"].append(str(cycle.id))
                self.summary["cycles"] += 1
            self.cycles[sprint["name"]] = cycle
        self.sprint_order = {s["name"]: i for i, s in enumerate(sprints)}

    def prepare_modules(self, rows: List[Row]) -> None:
        if not self.options["epics_as_modules"]:
            return
        taken = {m.name.lower() for m in Module.objects.filter(project=self.project)}
        for row in rows:
            if not is_epic(row):
                continue
            jira_id = first(row, "Issue id") or first(row, "Issue key")
            module = Module.objects.filter(project=self.project, external_source=SOURCE, external_id=jira_id).first()
            if module is None:
                name = (first(row, "Custom field (Epic Name)") or first(row, "Summary"))[:240]
                if name.lower() in taken:
                    name = f"{name} ({first(row, 'Issue key')})"
                taken.add(name.lower())
                status = self.states.get(first(row, "Status"))
                module = Module(
                    name=name,
                    description=first(row, "Description")[:5000],
                    project=self.project,
                    workspace=self.workspace,
                    status=MODULE_STATUS.get(status.group if status else "", "planned"),
                    lead_id=self.member(first(row, "Assignee Id"), first(row, "Assignee")),
                    start_date=parse_date(first(row, "Custom field (Start date)") or first(row, "Created"), self.tz),
                    target_date=parse_date(first(row, "Due date"), self.tz),
                    external_source=SOURCE,
                    external_id=jira_id,
                )
                module.save(created_by_id=self.initiator_id)
                self.created["modules"].append(str(module.id))
                self.summary["modules"] += 1
            self.modules[jira_id] = module
            self.modules[first(row, "Issue key")] = module

    # ------------------------------------------------------------------ work items

    def description_html(self, row: Row) -> str:
        body = jira_to_html(first(row, "Description"))
        notes = []
        if not self.keep_keys:
            notes.append(f"Jira: {first(row, 'Issue key')}")
        for column, id_column, label in (
            ("Assignee", "Assignee Id", "Assignee"),
            ("Reporter", "Reporter Id", "Reporter"),
        ):
            name = first(row, column)
            if name and not self.member(first(row, id_column), name):
                notes.append(f"{label} in Jira: {name}")
        if notes:
            body += "<p><em>" + html.escape(" · ".join(notes)) + "</em></p>"
        return body

    def epic_module(self, row: Row) -> Optional[Module]:
        parent = first(row, "Parent") or first(row, "Parent id")
        module = self.modules.get(parent) if parent else None
        if module is None:
            for column in EPIC_LINK_COLUMNS:
                if first(row, column) and first(row, column) in self.modules:
                    return self.modules[first(row, column)]
        return module

    def latest_cycle(self, row: Row) -> Optional[Cycle]:
        sprints = [s for s in row.get("Sprint", []) if s in self.cycles]
        if not sprints:
            return None
        return self.cycles[max(sprints, key=lambda s: self.sprint_order.get(s, -1))]

    def write_issue(self, row: Row) -> Issue:
        jira_id = first(row, "Issue id") or first(row, "Issue key")
        key = first(row, "Issue key")
        state = self.states.get(first(row, "Status"))
        priority = self.priority_map.get(first(row, "Priority") or "None", "none")
        if priority not in ("urgent", "high", "medium", "low", "none"):
            priority = "none"
        created = self.when(first(row, "Created"))
        updated = self.when(first(row, "Updated")) or created
        resolved = self.when(first(row, "Resolved"))
        points_raw = next((first(row, c) for c in STORY_POINT_COLUMNS if first(row, c)), "")
        estimate_point = None
        if points_raw and self.points:
            try:
                estimate_point = self.points.get(format(Decimal(points_raw).normalize(), "f"))
            except InvalidOperation:
                estimate_point = None
        reporter_id = self.member(first(row, "Reporter Id"), first(row, "Reporter")) or self.initiator_id

        fields = {
            "name": first(row, "Summary")[:255] or key,
            "description_html": self.description_html(row),
            "state": state,
            "priority": priority,
            "start_date": parse_date(first(row, "Custom field (Start date)") or first(row, "Start date"), self.tz),
            "target_date": parse_date(first(row, "Due date"), self.tz),
            "estimate_point": estimate_point,
        }

        issue = (
            Issue.all_objects.filter(
                project=self.project, external_source=SOURCE, external_id=jira_id, deleted_at__isnull=True
            )
            .order_by("created_at")
            .first()
        )
        is_new = issue is None
        if not is_new:
            if self.options["on_existing"] == "skip":
                self.summary["skipped"] += 1
                return issue
            for name, value in fields.items():
                setattr(issue, name, value)
            issue.save(created_by_id=reporter_id)
            self.summary["updated"] += 1
        else:
            issue = Issue(
                project=self.project, workspace=self.workspace, external_source=SOURCE, external_id=jira_id, **fields
            )
            issue.save(created_by_id=reporter_id)
            if self.keep_keys and issue_number(key):
                number = issue_number(key)
                Issue.all_objects.filter(pk=issue.pk).update(sequence_id=number)
                IssueSequence.objects.filter(issue=issue).update(sequence=number)
                issue.sequence_id = number
            self.created["issues"].append(str(issue.id))
            self.new_issue_ids.add(issue.id)
            self.summary["created"] += 1

        completed_at = None
        if state and state.group == "completed":
            completed_at = resolved or updated or created
        Issue.all_objects.filter(pk=issue.pk).update(
            created_at=created or issue.created_at,
            updated_at=updated or issue.updated_at,
            completed_at=completed_at,
        )

        # Relations replaced on update so a re-run matches the export
        assignees = self.people(row, "Assignee", "Assignee Id")
        if not is_new:
            IssueAssignee.objects.filter(issue=issue).exclude(assignee_id__in=assignees).delete()
        current = set(str(a) for a in IssueAssignee.objects.filter(issue=issue).values_list("assignee_id", flat=True))
        for member_id in assignees - current:
            IssueAssignee.objects.create(
                issue=issue,
                assignee_id=member_id,
                project=self.project,
                workspace=self.workspace,
                created_by_id=reporter_id,
            )

        label_names = list(row.get("Labels", []))
        if self.options["issue_types_as_labels"] and first(row, "Issue Type"):
            label_names.append(first(row, "Issue Type"))
        label_ids = {self.label(name).id for name in label_names if name.strip()}
        if not is_new:
            IssueLabel.objects.filter(issue=issue).exclude(label_id__in=label_ids).delete()
        current_labels = set(IssueLabel.objects.filter(issue=issue).values_list("label_id", flat=True))
        for label_id in label_ids - current_labels:
            IssueLabel.objects.create(
                issue=issue,
                label_id=label_id,
                project=self.project,
                workspace=self.workspace,
                created_by_id=reporter_id,
            )

        if self.options["watchers"]:
            watcher_ids = self.people(row, "Watchers", "Watchers Id")
            current_watchers = set(
                str(s) for s in IssueSubscriber.objects.filter(issue=issue).values_list("subscriber_id", flat=True)
            )
            for member_id in watcher_ids - current_watchers:
                IssueSubscriber.objects.create(
                    issue=issue, subscriber_id=member_id, project=self.project, workspace=self.workspace
                )

        cycle = self.latest_cycle(row)
        if cycle:
            link = CycleIssue.objects.filter(issue=issue).first()
            if link is None:
                CycleIssue.objects.create(issue=issue, cycle=cycle, project=self.project, workspace=self.workspace)
            elif link.cycle_id != cycle.id:
                CycleIssue.objects.filter(pk=link.pk).update(cycle=cycle)

        module = self.epic_module(row)
        if module and not ModuleIssue.objects.filter(issue=issue, module=module).exists():
            ModuleIssue.objects.create(issue=issue, module=module, project=self.project, workspace=self.workspace)

        if is_new:
            activity = IssueActivity.objects.create(
                issue=issue,
                actor_id=reporter_id,
                project=self.project,
                workspace=self.workspace,
                verb="created",
                comment="created the work item",
                created_by_id=reporter_id,
            )
            if created:
                IssueActivity.objects.filter(pk=activity.pk).update(created_at=created)
        return issue

    # ------------------------------------------------------------------ second pass

    def write_parent(self, row: Row, issue: Issue) -> None:
        parent_ref = first(row, "Parent") or first(row, "Parent id")
        parent = self.issue_by_id.get(parent_ref) if parent_ref else None
        if parent is None:
            for column in EPIC_LINK_COLUMNS:
                ref = first(row, column)
                if ref and ref in self.issue_by_key:
                    parent = self.issue_by_key[ref]
                    break
        if parent and parent.id != issue.id and issue.parent_id != parent.id:
            Issue.all_objects.filter(pk=issue.pk).update(parent=parent)

    def write_relations(self, row: Row, issue: Issue) -> None:
        for header, values in row.items():
            if not header.startswith(LINK_PREFIXES):
                continue
            inward = header.startswith("Inward")
            link_type = header[header.find("(") + 1 : header.rfind(")")].strip().lower()
            for ref in values:
                other = self.issue_by_key.get(ref) or self.issue_by_id.get(ref)
                if other is None or other.id == issue.id:
                    continue
                if link_type == "blocks":
                    # Outward "blocks": this blocks other -> other is blocked by this
                    source, target, kind = (issue, other, "blocked_by") if inward else (other, issue, "blocked_by")
                elif link_type == "duplicate":
                    source, target, kind = (other, issue, "duplicate") if inward else (issue, other, "duplicate")
                else:
                    source, target, kind = issue, other, "relates_to"
                exists = IssueRelation.objects.filter(
                    Q(issue=source, related_issue=target) | Q(issue=target, related_issue=source)
                ).exists()
                if not exists:
                    IssueRelation.objects.create(
                        issue=source,
                        related_issue=target,
                        relation_type=kind,
                        project=self.project,
                        workspace=self.workspace,
                        created_by_id=self.initiator_id,
                    )
                    self.summary["relations"] += 1

    def write_comments(self, row: Row, issue: Issue) -> None:
        jira_id = first(row, "Issue id") or first(row, "Issue key")
        names = self.account_names
        for index, value in enumerate(row.get("Comment", [])):
            external_id = f"{jira_id}:{index}"
            if IssueComment.objects.filter(issue=issue, external_source=SOURCE, external_id=external_id).exists():
                continue
            when, account_id, body = comment_parts(value)
            actor_id = self.member(account_id) or self.initiator_id
            comment_html = jira_to_html(body)
            if not self.member(account_id):
                author = names.get(account_id) or account_id or "Jira"
                comment_html = f"<p><em>{html.escape(author)}</em></p>" + comment_html
            comment = IssueComment(
                issue=issue,
                project=self.project,
                workspace=self.workspace,
                actor_id=actor_id,
                comment_html=comment_html,
                external_source=SOURCE,
                external_id=external_id,
            )
            comment.save(created_by_id=actor_id)
            posted = self.when(when)
            if posted:
                IssueComment.objects.filter(pk=comment.pk).update(created_at=posted, updated_at=posted)
            self.created["comments"].append(str(comment.id))
            self.summary["comments"] += 1

    def write_attachments(self, row: Row, issue: Issue) -> None:
        for value in row.get("Attachment", []):
            _, _, file_name, url = attachment_parts(value)
            if not url.startswith(("http://", "https://")):
                continue
            if IssueLink.objects.filter(issue=issue, url=url).exists():
                continue
            link = IssueLink(
                issue=issue,
                title=(file_name or url)[:255],
                url=url,
                project=self.project,
                workspace=self.workspace,
                metadata={"source": SOURCE},
            )
            link.save(created_by_id=self.initiator_id)
            self.created["links"].append(str(link.id))
            self.summary["links"] += 1

    # ------------------------------------------------------------------ main

    def run(self) -> None:
        rows = read_rows(load_file(self.job.file_key))
        jira_project = (self.config.get("target") or {}).get("jira_project")
        if jira_project:
            rows = [r for r in rows if (first(r, "Project key") or project_key(first(r, "Issue key"))) == jira_project]
        rows.sort(key=lambda r: issue_number(first(r, "Issue key")))

        self.account_names = {}
        for row in rows:
            for name_col, id_col in (
                ("Assignee", "Assignee Id"),
                ("Reporter", "Reporter Id"),
                ("Creator", "Creator Id"),
            ):
                for account_id, name in zip(row.get(id_col, []), row.get(name_col, [])):
                    self.account_names.setdefault(account_id, name)

        with transaction.atomic():
            self.prepare_project()
            self.prepare_states(rows)
            self.prepare_estimates(rows)
            self.prepare_cycles()
            self.prepare_modules(rows)

        items = [r for r in rows if not (self.options["epics_as_modules"] and is_epic(r))]
        JiraImport.objects.filter(pk=self.job.pk).update(
            project=self.project, created_project=self.job.created_project, total=len(items) * 2, processed=0
        )

        written: List[tuple] = []
        for index, row in enumerate(items):
            key = first(row, "Issue key")
            try:
                with transaction.atomic():
                    issue = self.write_issue(row)
                self.issue_by_id[first(row, "Issue id")] = issue
                self.issue_by_key[key] = issue
                written.append((index, row, issue))
            except Exception as exc:  # noqa: BLE001 - recorded per row and skipped
                self.error(index, key, exc)
            if (index + 1) % PROGRESS_EVERY == 0:
                self.save_progress(index + 1)
                self.checkpoint()

        for position, (index, row, issue) in enumerate(written):
            try:
                with transaction.atomic():
                    self.write_parent(row, issue)
                    self.write_relations(row, issue)
                    if self.options["comments"] and (
                        issue.id in self.new_issue_ids or self.options["on_existing"] == "update"
                    ):
                        self.write_comments(row, issue)
                    if self.options["attachments"] and (
                        issue.id in self.new_issue_ids or self.options["on_existing"] == "update"
                    ):
                        self.write_attachments(row, issue)
            except Exception as exc:  # noqa: BLE001
                self.error(index, first(row, "Issue key"), exc)
            if (position + 1) % PROGRESS_EVERY == 0:
                self.save_progress(len(items) + position + 1)

        self.checkpoint()
        JiraImport.objects.filter(pk=self.job.pk).update(processed=len(items) * 2)

    def checkpoint(self) -> None:
        """Persist ids created so far, so an interrupted import can still be undone."""
        JiraImport.objects.filter(pk=self.job.pk).update(
            created_ids=self.created, summary=self.summary, errors=self.errors
        )


def can_keep_keys(project: Project) -> bool:
    """Jira numbers can be kept when the project has no work items other than earlier Jira imports."""
    return not Issue.all_objects.filter(project=project).exclude(external_source=SOURCE).exists()


def run_import(job: JiraImport) -> None:
    run = ImportRun(job)
    JiraImport.objects.filter(pk=job.pk).update(status=JiraImport.Status.RUNNING, started_at=timezone.now())
    try:
        run.run()
        status = JiraImport.Status.COMPLETED
    except Exception as exc:  # noqa: BLE001 - the job records the failure
        run.errors.insert(0, {"row": None, "key": None, "message": str(exc)[:300]})
        status = JiraImport.Status.FAILED
    JiraImport.objects.filter(pk=job.pk).update(
        status=status,
        finished_at=timezone.now(),
        created_ids=run.created,
        summary=run.summary,
        errors=run.errors[:MAX_ERRORS],
        project=run.project,
        created_project=run.job.created_project,
    )


def undo_import(job: JiraImport) -> None:
    """Soft-delete everything the import created. Updates to items that already existed are kept."""
    created = job.created_ids or {}
    issue_ids = created.get("issues", [])
    with transaction.atomic():
        for model in (IssueAssignee, IssueLabel, IssueSubscriber, CycleIssue, ModuleIssue, IssueLink, IssueComment):
            model.objects.filter(issue_id__in=issue_ids).delete()
        IssueRelation.objects.filter(Q(issue_id__in=issue_ids) | Q(related_issue_id__in=issue_ids)).delete()
        IssueActivity.objects.filter(issue_id__in=issue_ids).delete()
        Issue.objects.filter(id__in=issue_ids).delete()
        IssueComment.objects.filter(id__in=created.get("comments", [])).delete()
        IssueLink.objects.filter(id__in=created.get("links", [])).delete()
        CycleIssue.objects.filter(cycle_id__in=created.get("cycles", [])).delete()
        ModuleIssue.objects.filter(module_id__in=created.get("modules", [])).delete()
        Cycle.objects.filter(id__in=created.get("cycles", [])).delete()
        Module.objects.filter(id__in=created.get("modules", [])).delete()
        IssueLabel.objects.filter(label_id__in=created.get("labels", [])).delete()
        Label.objects.filter(id__in=created.get("labels", [])).delete()
        EstimatePoint.objects.filter(id__in=created.get("estimate_points", [])).delete()
        Project.objects.filter(estimate_id__in=created.get("estimates", [])).update(estimate=None)
        Estimate.objects.filter(id__in=created.get("estimates", [])).delete()
        State.objects.filter(id__in=created.get("states", [])).delete()
        ProjectMember.objects.filter(id__in=created.get("project_members", [])).delete()
        for project in Project.objects.filter(id__in=created.get("projects", [])):
            ProjectIdentifier.objects.filter(project=project).delete()
            project.delete()
