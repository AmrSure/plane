/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TJiraImportDetail } from "@plane/types";
// local
import { JiraImportProgressBar, JiraImportSummary } from "../summary";

type Props = {
  detail: TJiraImportDetail;
};

export function JiraImportProgressStep(props: Props) {
  const { detail } = props;
  const { t } = useTranslation();
  const running = detail.status === "queued" || detail.status === "running";

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        {running && <Loader2 className="size-6 animate-spin text-accent-primary" />}
        {detail.status === "completed" && detail.error_count === 0 && (
          <CheckCircle2 className="size-6 text-success-primary" />
        )}
        {detail.status === "completed" && detail.error_count > 0 && (
          <AlertTriangle className="size-6 text-warning-primary" />
        )}
        {detail.status === "failed" && <XCircle className="size-6 text-danger-primary" />}
        <div>
          <div className="text-14 font-medium text-primary">{t(`importer.progress.title_${detail.status}`)}</div>
          <div className="text-12 text-tertiary">
            {running ? t("importer.progress.running_hint") : t("importer.progress.done_hint")}
          </div>
        </div>
      </div>

      <JiraImportProgressBar job={detail} />
      {!running && <JiraImportSummary job={detail} />}

      {detail.errors.length > 0 && !running && (
        <div className="space-y-1">
          <div className="text-13 font-medium text-primary">
            {t("importer.progress.errors_title", { count: detail.errors.length })}
          </div>
          <ul className="max-h-48 divide-y divide-subtle overflow-y-auto rounded-md border border-subtle text-12">
            {detail.errors.map((error, index) => (
              <li key={index} className="px-3 py-1.5">
                {error.key && <span className="me-2 font-medium text-primary">{error.key}</span>}
                <span className="text-secondary">{error.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
