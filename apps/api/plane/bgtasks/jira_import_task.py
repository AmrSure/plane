# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from celery import shared_task

# Django imports
from django.utils import timezone

# Module imports
from plane.db.models import JiraImport
from plane.utils.exception_logger import log_exception
from plane.utils.jira_import.runner import run_import, undo_import


@shared_task
def run_jira_import(job_id):
    job = JiraImport.objects.filter(pk=job_id).select_related("workspace").first()
    if job is None or job.status not in (JiraImport.Status.QUEUED, JiraImport.Status.RUNNING):
        return
    try:
        run_import(job)
    except Exception as exc:  # noqa: BLE001
        log_exception(exc)
        JiraImport.objects.filter(pk=job_id).update(
            status=JiraImport.Status.FAILED,
            finished_at=timezone.now(),
            errors=[{"row": None, "key": None, "message": str(exc)[:300]}],
        )


@shared_task
def undo_jira_import(job_id):
    job = JiraImport.objects.filter(pk=job_id).first()
    if job is None or job.status != JiraImport.Status.UNDOING:
        return
    try:
        undo_import(job)
        JiraImport.objects.filter(pk=job_id).update(status=JiraImport.Status.UNDONE, finished_at=timezone.now())
    except Exception as exc:  # noqa: BLE001
        log_exception(exc)
        # Undo runs in one transaction, so a failure leaves the import as it was and it can be retried
        JiraImport.objects.filter(pk=job_id).update(status=JiraImport.Status.COMPLETED)
