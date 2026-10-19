# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Import work items from a Jira CSV export.

Workspace admins can import into any project or create a new one. Project admins can
import only into the projects they administer.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.bgtasks.jira_import_task import run_jira_import, undo_jira_import
from plane.db.models import (
    JiraImport,
    Project,
    ProjectIdentifier,
    ProjectMember,
    State,
    Workspace,
    WorkspaceMember,
)
from plane.utils.jira_import.analyzer import analyze
from plane.utils.jira_import.dates import safe_zone
from plane.utils.jira_import.reader import JiraCsvError, read_rows
from plane.utils.jira_import.runner import DEFAULT_OPTIONS, can_keep_keys
from plane.utils.jira_import.storage import delete_file, store_file

ADMIN, MEMBER = 20, 15
PRIORITIES = ("urgent", "high", "medium", "low", "none")
GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")
ACTIVE = (JiraImport.Status.QUEUED, JiraImport.Status.RUNNING, JiraImport.Status.UNDOING)
FINISHED = (JiraImport.Status.COMPLETED, JiraImport.Status.FAILED)


def error(message: str, code: str, http_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": message, "code": code}, status=http_status)


def forbidden() -> Response:
    return error("You don't have permission to import work items.", "forbidden", status.HTTP_403_FORBIDDEN)


def not_found() -> Response:
    return error("Import not found.", "not_found", status.HTTP_404_NOT_FOUND)


class Access:
    """What the requesting user may do with Jira imports in a workspace."""

    def __init__(self, user, slug: str):
        self.user = user
        self.member = (
            WorkspaceMember.objects.filter(workspace__slug=slug, member=user, is_active=True)
            .select_related("workspace")
            .first()
        )
        self.workspace: Optional[Workspace] = self.member.workspace if self.member else None
        self.is_admin = bool(self.member and self.member.role == ADMIN)
        self.admin_project_ids = set()
        if self.member and self.member.role >= MEMBER:
            self.admin_project_ids = {
                str(pid)
                for pid in ProjectMember.objects.filter(
                    workspace=self.workspace,
                    member=user,
                    role=ADMIN,
                    is_active=True,
                    project__archived_at__isnull=True,
                ).values_list("project_id", flat=True)
            }

    @property
    def allowed(self) -> bool:
        return self.is_admin or bool(self.admin_project_ids)

    def projects(self):
        queryset = Project.objects.filter(workspace=self.workspace, archived_at__isnull=True)
        if not self.is_admin:
            queryset = queryset.filter(id__in=self.admin_project_ids)
        return queryset.order_by("name")

    def jobs(self):
        queryset = JiraImport.objects.filter(workspace=self.workspace).select_related("project", "initiated_by")
        return queryset if self.is_admin else queryset.filter(initiated_by=self.user)

    def job(self, pk) -> Optional[JiraImport]:
        """Admins see every import in the workspace; project admins only their own."""
        return self.jobs().filter(pk=pk).first() if self.allowed else None


def job_data(job: JiraImport, detail: bool = False) -> Dict[str, Any]:
    project = job.project if job.project_id else None
    data = {
        "id": str(job.id),
        "status": job.status,
        "file_name": job.file_name,
        "file_size": job.file_size,
        "project": (
            {"id": str(project.id), "name": project.name, "identifier": project.identifier}
            if project is not None and project.deleted_at is None
            else None
        ),
        "created_project": job.created_project,
        "initiated_by": (
            {"id": str(job.initiated_by_id), "display_name": job.initiated_by.display_name}
            if job.initiated_by_id
            else None
        ),
        "work_item_count": (job.analysis or {}).get("work_item_count", 0),
        "processed": job.processed,
        "total": job.total,
        "summary": job.summary or {},
        "error_count": len(job.errors or []),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
    if detail:
        data["errors"] = job.errors or []
        data["analysis"] = job.analysis or {}
        data["config"] = job.config or {}
    return data


def member_rows(workspace: Workspace) -> List[Dict[str, Any]]:
    rows = WorkspaceMember.objects.filter(workspace=workspace, is_active=True, member__is_bot=False).select_related(
        "member"
    )
    return [
        {
            "id": str(m.member_id),
            "display_name": m.member.display_name,
            "first_name": m.member.first_name,
            "last_name": m.member.last_name,
            "email": m.member.email,
            "avatar_url": m.member.avatar_url,
            "role": m.role,
        }
        for m in rows
    ]


def identifier_problem(workspace: Workspace, identifier: str) -> Optional[str]:
    if not identifier or len(identifier) > 12:
        return "identifier_length"
    if re.match(Project.FORBIDDEN_IDENTIFIER_CHARS_PATTERN, identifier) or " " in identifier:
        return "identifier_invalid"
    if (
        ProjectIdentifier.objects.filter(workspace=workspace, name=identifier).exists()
        or Project.objects.filter(workspace=workspace, identifier=identifier).exists()
    ):
        return "identifier_taken"
    return None


def suggested_identifier(workspace: Workspace, key: str) -> Dict[str, Any]:
    identifier = re.sub(r"[^A-Z0-9]", "", (key or "").upper())[:12]
    return {
        "identifier": identifier,
        "available": bool(identifier) and identifier_problem(workspace, identifier) is None,
    }


def options_data(access: Access, job: JiraImport) -> Dict[str, Any]:
    """Everything the wizard needs to map the export: target projects, their states, members."""
    projects = list(access.projects())
    states: Dict[str, List[Dict[str, Any]]] = {str(p.id): [] for p in projects}
    for state in State.objects.filter(project__in=projects).order_by("sequence"):
        states[str(state.project_id)].append({"id": str(state.id), "name": state.name, "group": state.group})
    jira_projects = (job.analysis or {}).get("projects") or []
    return {
        "can_create_project": access.is_admin,
        "suggested_identifier": suggested_identifier(
            access.workspace, jira_projects[0]["key"] if jira_projects else ""
        ),
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "identifier": p.identifier,
                "can_keep_keys": can_keep_keys(p),
                "states": states[str(p.id)],
            }
            for p in projects
        ],
        "members": member_rows(access.workspace),
        "default_options": DEFAULT_OPTIONS,
    }


class JiraImportEndpoint(BaseAPIView):
    def get(self, request, slug):
        access = Access(request.user, slug)
        if not access.allowed:
            return forbidden()
        return Response([job_data(job) for job in access.jobs()[:100]])

    def post(self, request, slug):
        access = Access(request.user, slug)
        if not access.allowed:
            return forbidden()
        upload = request.FILES.get("file")
        if upload is None:
            return error("Choose a CSV file exported from Jira.", "missing_file")
        if not upload.name.lower().endswith(".csv"):
            return error("The file must be a CSV export from Jira.", "invalid_type")
        if upload.size > settings.FILE_SIZE_LIMIT:
            return error("The file is larger than the upload limit.", "file_too_large")
        content = upload.read()
        try:
            rows = read_rows(content)
        except JiraCsvError as exc:
            return error("The file is not a usable Jira CSV export.", str(exc))

        tz_name = request.data.get("timezone") or request.user.user_timezone or access.workspace.timezone
        analysis = analyze(rows, member_rows(access.workspace), safe_zone(tz_name))
        analysis["timezone"] = tz_name

        file_key = f"{access.workspace.id}/jira-imports/{uuid.uuid4().hex}.csv"
        if not store_file(file_key, content):
            return error(
                "The file could not be stored. Try again.", "storage_failed", status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        job = JiraImport.objects.create(
            workspace=access.workspace,
            initiated_by=request.user,
            file_key=file_key,
            file_name=upload.name[:255],
            file_size=upload.size,
            analysis=analysis,
        )
        return Response(
            {**job_data(job, detail=True), "options": options_data(access, job)}, status=status.HTTP_201_CREATED
        )


class JiraImportDetailEndpoint(BaseAPIView):
    def get(self, request, slug, pk):
        access = Access(request.user, slug)
        job = access.job(pk)
        if job is None:
            return not_found()
        data = job_data(job, detail=True)
        if request.GET.get("options") == "true":
            data["options"] = options_data(access, job)
        return Response(data)

    def delete(self, request, slug, pk):
        access = Access(request.user, slug)
        job = access.job(pk)
        if job is None:
            return not_found()
        if job.status in ACTIVE:
            return error("Wait for the import to finish before removing it.", "import_active", status.HTTP_409_CONFLICT)
        delete_file(job.file_key)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JiraImportStartEndpoint(BaseAPIView):
    def validate(
        self, access: Access, job: JiraImport, data: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Response]]:
        analysis = job.analysis or {}
        jira_keys = [p["key"] for p in analysis.get("projects") or []]
        target = data.get("target") or {}
        jira_project = target.get("jira_project") or (jira_keys[0] if len(jira_keys) == 1 else None)
        if jira_project and jira_project not in jira_keys:
            return None, error("Choose a Jira project from the file.", "invalid_jira_project")

        # A re-run goes into the project the earlier run used
        if job.status in FINISHED and job.project_id:
            target = {"mode": "existing", "project_id": str(job.project_id)}

        project = None
        if target.get("mode") == "new":
            if not access.is_admin:
                return None, error(
                    "Only workspace admins can create a project.", "forbidden", status.HTTP_403_FORBIDDEN
                )
            name = (target.get("name") or "").strip()
            identifier = (target.get("identifier") or "").strip().upper()
            if not name or len(name) > 255 or re.match(Project.FORBIDDEN_IDENTIFIER_CHARS_PATTERN, name):
                return None, error("Enter a project name without special characters.", "invalid_name")
            if Project.objects.filter(workspace=access.workspace, name=name).exists():
                return None, error("A project with this name already exists.", "name_taken")
            problem = identifier_problem(access.workspace, identifier)
            if problem:
                return None, error("Choose another project identifier.", problem)
            target = {"mode": "new", "name": name, "identifier": identifier}
        elif target.get("mode") == "existing":
            project = access.projects().filter(pk=target.get("project_id")).first()
            if project is None:
                return None, error("You can't import into this project.", "forbidden", status.HTTP_403_FORBIDDEN)
            target = {"mode": "existing", "project_id": str(project.id)}
        else:
            return None, error("Choose where to import the work items.", "missing_target")
        target["jira_project"] = jira_project

        status_map: Dict[str, Dict[str, Any]] = {}
        known_statuses = {s["name"] for s in analysis.get("statuses") or []}
        for name, choice in (data.get("status_map") or {}).items():
            if name not in known_statuses or not isinstance(choice, dict):
                continue
            if choice.get("mode") == "existing":
                if project is None or not State.objects.filter(project=project, pk=choice.get("state_id")).exists():
                    return None, error(f"Choose a valid state for {name}.", "invalid_state")
                status_map[name] = {"mode": "existing", "state_id": str(choice["state_id"])}
            else:
                group = choice.get("group") if choice.get("group") in GROUPS else "unstarted"
                status_map[name] = {"mode": "create", "group": group}
        for entry in analysis.get("statuses") or []:
            status_map.setdefault(entry["name"], {"mode": "create", "group": entry.get("suggested_group", "unstarted")})

        priority_map = {}
        chosen_priorities = data.get("priority_map") or {}
        for entry in analysis.get("priorities") or []:
            chosen = chosen_priorities.get(entry["name"], entry.get("suggested", "none"))
            priority_map[entry["name"]] = chosen if chosen in PRIORITIES else "none"

        members = {m["id"] for m in member_rows(access.workspace)}
        user_keys = {u["id"] for u in analysis.get("users") or []}
        user_map: Dict[str, Optional[str]] = {}
        for key, member_id in (data.get("user_map") or {}).items():
            if key not in user_keys:
                continue
            if member_id and str(member_id) not in members:
                return None, error("Map people to active workspace members.", "invalid_member")
            user_map[key] = str(member_id) if member_id else None

        raw_options = data.get("options") or {}
        options: Dict[str, Any] = {
            key: bool(raw_options.get(key, default)) for key, default in DEFAULT_OPTIONS.items() if key != "on_existing"
        }
        options["on_existing"] = "skip" if raw_options.get("on_existing") == "skip" else "update"

        return {
            "target": target,
            "status_map": status_map,
            "priority_map": priority_map,
            "user_map": user_map,
            "options": options,
            "timezone": analysis.get("timezone") or access.workspace.timezone,
            # A re-run keeps the ids of earlier runs, so undo removes everything this import ever created
            "resume_created": job.status in FINISHED,
        }, None

    def post(self, request, slug, pk):
        access = Access(request.user, slug)
        job = access.job(pk)
        if job is None:
            return not_found()
        if job.status in ACTIVE:
            return error("This import is already running.", "import_active", status.HTTP_409_CONFLICT)
        config, problem = self.validate(access, job, request.data)
        if problem:
            return problem
        updates: Dict[str, Any] = {
            "config": config,
            "status": JiraImport.Status.QUEUED,
            "processed": 0,
            "total": 0,
            "errors": [],
            "finished_at": None,
        }
        if not config["resume_created"]:
            updates.update(project=None, created_project=False, created_ids={}, summary={})
        JiraImport.objects.filter(pk=job.pk).update(**updates)
        run_jira_import.delay(str(job.id))
        job.refresh_from_db()
        return Response(job_data(job, detail=True), status=status.HTTP_202_ACCEPTED)


class JiraImportUndoEndpoint(BaseAPIView):
    def post(self, request, slug, pk):
        access = Access(request.user, slug)
        job = access.job(pk)
        if job is None:
            return not_found()
        if job.status not in FINISHED:
            return error("Only finished imports can be undone.", "not_undoable", status.HTTP_409_CONFLICT)
        JiraImport.objects.filter(pk=job.pk).update(status=JiraImport.Status.UNDOING)
        undo_jira_import.delay(str(job.id))
        job.refresh_from_db()
        return Response(job_data(job, detail=True), status=status.HTTP_202_ACCEPTED)
