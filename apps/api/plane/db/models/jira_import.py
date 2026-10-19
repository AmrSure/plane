# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from .base import BaseModel


class JiraImport(BaseModel):
    """One import of a Jira CSV export into a project."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        UNDOING = "undoing", "Undoing"
        UNDONE = "undone", "Undone"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="jira_imports")
    # Target project; set when the import starts (created by the import or chosen by the user)
    project = models.ForeignKey(
        "db.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="jira_imports"
    )
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jira_imports")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    file_key = models.CharField(max_length=512)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    # Result of analysing the CSV: projects, statuses, users, sprints, warnings...
    analysis = models.JSONField(default=dict)
    # Mappings and options chosen by the user when starting the import
    config = models.JSONField(default=dict)
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict)
    errors = models.JSONField(default=list)
    # Ids of everything this import created, used to undo it
    created_ids = models.JSONField(default=dict)
    created_project = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Jira Import"
        verbose_name_plural = "Jira Imports"
        db_table = "jira_imports"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["workspace", "status"], name="jira_import_ws_status_idx")]

    def __str__(self):
        return f"{self.file_name} <{self.workspace_id}> {self.status}"
