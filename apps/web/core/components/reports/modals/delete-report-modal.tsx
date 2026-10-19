/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TSavedReport } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
// hooks
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";
import { useAppRouter } from "@/hooks/use-app-router";

type Props = {
  workspaceSlug: string;
  report: TSavedReport;
  isOpen: boolean;
  onClose: () => void;
  redirectOnDelete?: boolean;
};

export const DeleteReportModal = observer(function DeleteReportModal(props: Props) {
  const { workspaceSlug, report, isOpen, onClose, redirectOnDelete = false } = props;
  const { t } = useTranslation();
  const router = useAppRouter();
  const { deleteReport } = useWorkspaceReport();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteReport(workspaceSlug, report.id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("reports.delete.success") });
      onClose();
      if (redirectOnDelete) router.push(`/${workspaceSlug}/reports`);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("reports.toast.error") });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <AlertModalCore
      isOpen={isOpen}
      handleClose={onClose}
      handleSubmit={handleDelete}
      isSubmitting={isDeleting}
      title={t("reports.delete.title")}
      content={<>{t("reports.delete.description", { name: report.name })}</>}
      primaryButtonText={{ loading: t("dashboards.delete.deleting"), default: t("dashboards.delete.confirm") }}
      secondaryButtonText={t("cancel")}
    />
  );
});
