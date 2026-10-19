/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import type { TJiraImport, TJiraImportStatus, TJiraImportSummary } from "@plane/types";
import { cn } from "@plane/utils";

const SUMMARY_KEYS: (keyof TJiraImportSummary)[] = [
  "created",
  "updated",
  "skipped",
  "failed",
  "cycles",
  "modules",
  "states",
  "labels",
  "comments",
  "links",
  "relations",
];

export function JiraImportStatusBadge(props: { status: TJiraImportStatus }) {
  const { status } = props;
  const { t } = useTranslation();
  return (
    <span
      className={cn("inline-flex items-center rounded-sm px-2 py-0.5 text-11 font-medium", {
        "bg-layer-2 text-secondary": status === "uploaded" || status === "undone",
        "bg-accent-subtle text-accent-primary": status === "queued" || status === "running" || status === "undoing",
        "bg-success-subtle text-success-primary": status === "completed",
        "bg-danger-subtle text-danger-primary": status === "failed",
      })}
    >
      {t(`importer.status.${status}`)}
    </span>
  );
}

export function JiraImportProgressBar(props: { job: TJiraImport }) {
  const { job } = props;
  const percent = job.total > 0 ? Math.min(100, Math.round((job.processed / job.total) * 100)) : 0;
  const done = job.status === "completed" || job.status === "failed";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-layer-2">
      <div
        className={cn("h-full rounded-full bg-accent-primary transition-all", { "bg-success-primary": done })}
        style={{ width: `${done ? 100 : percent}%` }}
      />
    </div>
  );
}

export function JiraImportSummary(props: { job: TJiraImport }) {
  const { job } = props;
  const { t } = useTranslation();
  const entries = SUMMARY_KEYS.filter((key) => (job.summary[key] ?? 0) > 0);
  if (entries.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {entries.map((key) => (
        <div key={key} className="rounded-md bg-layer-1 px-3 py-2">
          <dt className="text-11 text-tertiary">{t(`importer.summary.${key}`)}</dt>
          <dd className={cn("text-16 font-medium text-primary", { "text-danger-primary": key === "failed" })}>
            {job.summary[key]}
          </dd>
        </div>
      ))}
    </dl>
  );
}
