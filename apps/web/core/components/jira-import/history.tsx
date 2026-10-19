/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TJiraImport } from "@plane/types";
import { AlertModalCore, CustomMenu, Loader } from "@plane/ui";
import { calculateTimeAgo } from "@plane/utils";
// assets
import jiraLogo from "@/app/assets/services/jira.svg?url";
// services
import { JiraImportService } from "@/services/jira-import.service";
// local
import { ACTIVE_STATUSES, formatBytes } from "./helpers";
import { JiraImportModal } from "./import-modal";
import { JiraImportProgressBar, JiraImportStatusBadge, JiraImportSummary } from "./summary";

const service = new JiraImportService();

type TPendingAction = { kind: "undo" | "delete"; job: TJiraImport } | null;

export const JiraImportsRoot = observer(function JiraImportsRoot(props: { workspaceSlug: string }) {
  const { workspaceSlug } = props;
  const { t } = useTranslation();
  const [modal, setModal] = useState<{ open: boolean; importId: string | null }>({ open: false, importId: null });
  const [pending, setPending] = useState<TPendingAction>(null);
  const [working, setWorking] = useState(false);

  const { data, error, mutate, isLoading } = useSWR(
    ["jira-imports", workspaceSlug],
    () => service.list(workspaceSlug),
    {
      refreshInterval: (latest) => (latest?.some((job) => ACTIVE_STATUSES.includes(job.status)) ? 2000 : 0),
      shouldRetryOnError: false,
    }
  );
  const forbidden = (error as { code?: string } | undefined)?.code === "forbidden";

  const confirm = async () => {
    if (!pending) return;
    setWorking(true);
    try {
      if (pending.kind === "undo") await service.undo(workspaceSlug, pending.job.id);
      else await service.destroy(workspaceSlug, pending.job.id);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t(pending.kind === "undo" ? "importer.toast.undo_started" : "importer.toast.deleted"),
      });
      setPending(null);
      void mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("importer.errors.generic") });
    } finally {
      setWorking(false);
    }
  };

  if (forbidden) {
    return <div className="rounded-md border border-subtle p-6 text-13 text-secondary">{t("importer.no_access")}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-lg border border-subtle p-5 sm:flex-row sm:items-center">
        <img src={jiraLogo} alt="" className="size-10 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-14 font-medium text-primary">{t("importer.jira.title")}</div>
          <div className="text-12 text-tertiary">{t("importer.jira.description")}</div>
        </div>
        <Button variant="primary" onClick={() => setModal({ open: true, importId: null })}>
          {t("importer.jira.start")}
        </Button>
      </div>

      <div className="space-y-2">
        <h4 className="text-14 font-medium text-primary">{t("importer.history.title")}</h4>
        {isLoading ? (
          <Loader className="space-y-2">
            <Loader.Item height="72px" />
            <Loader.Item height="72px" />
          </Loader>
        ) : data && data.length > 0 ? (
          <ul className="divide-y divide-subtle rounded-md border border-subtle">
            {data.map((job) => {
              const active = ACTIVE_STATUSES.includes(job.status);
              const finished = job.status === "completed" || job.status === "failed";
              return (
                <li key={job.id} className="space-y-2 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="truncate text-13 font-medium text-primary">{job.file_name}</span>
                    <JiraImportStatusBadge status={job.status} />
                    {job.project && (
                      <Link
                        href={`/${workspaceSlug}/projects/${job.project.id}/issues`}
                        className="text-12 text-accent-primary hover:underline"
                      >
                        {job.project.identifier} · {job.project.name}
                      </Link>
                    )}
                    <span className="ms-auto text-12 text-tertiary">
                      {t("importer.history.meta", {
                        items: job.work_item_count,
                        size: formatBytes(job.file_size),
                        who: job.initiated_by?.display_name ?? "",
                        when: calculateTimeAgo(job.created_at),
                      })}
                    </span>
                    {!active && (
                      <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
                        {(job.status === "uploaded" || finished) && (
                          <CustomMenu.MenuItem onClick={() => setModal({ open: true, importId: job.id })}>
                            {job.status === "uploaded" ? t("importer.history.continue") : t("importer.history.rerun")}
                          </CustomMenu.MenuItem>
                        )}
                        {finished && (
                          <CustomMenu.MenuItem onClick={() => setPending({ kind: "undo", job })}>
                            {t("importer.history.undo")}
                          </CustomMenu.MenuItem>
                        )}
                        <CustomMenu.MenuItem onClick={() => setPending({ kind: "delete", job })}>
                          <span className="text-danger-primary">{t("importer.history.delete")}</span>
                        </CustomMenu.MenuItem>
                      </CustomMenu>
                    )}
                  </div>
                  {active && <JiraImportProgressBar job={job} />}
                  {finished && <JiraImportSummary job={job} />}
                  {job.error_count > 0 && finished && (
                    <p className="text-12 text-danger-primary">
                      {t("importer.history.errors", { count: job.error_count })}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyStateCompact
            assetKey="export"
            title={t("importer.history.empty_title")}
            description={t("importer.history.empty_description")}
            align="start"
            rootClassName="py-12"
          />
        )}
      </div>

      <JiraImportModal
        workspaceSlug={workspaceSlug}
        isOpen={modal.open}
        importId={modal.importId}
        onClose={() => {
          setModal({ open: false, importId: null });
          void mutate();
        }}
        onChanged={() => void mutate()}
      />

      <AlertModalCore
        isOpen={Boolean(pending)}
        handleClose={() => setPending(null)}
        handleSubmit={confirm}
        isSubmitting={working}
        variant={pending?.kind === "undo" ? "primary" : "danger"}
        title={pending?.kind === "undo" ? t("importer.undo.title") : t("importer.delete.title")}
        content={
          <>
            {pending?.kind === "undo"
              ? t(pending.job.created_project ? "importer.undo.description_project" : "importer.undo.description", {
                  project: pending.job.project?.name ?? "",
                })
              : t("importer.delete.description")}
          </>
        }
        primaryButtonText={{
          loading: t("importer.common.working"),
          default: pending?.kind === "undo" ? t("importer.undo.confirm") : t("importer.delete.confirm"),
        }}
        secondaryButtonText={t("cancel")}
      />
    </div>
  );
});
