/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TWorkspaceDashboard } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { useAppRouter } from "@/hooks/use-app-router";

type Props = {
  workspaceSlug: string;
  dashboard: TWorkspaceDashboard;
  isOpen: boolean;
  onClose: () => void;
  redirectOnDelete?: boolean;
};

export const DeleteDashboardModal = observer(function DeleteDashboardModal(props: Props) {
  const { workspaceSlug, dashboard, isOpen, onClose, redirectOnDelete = false } = props;
  const { t } = useTranslation();
  const router = useAppRouter();
  const { deleteDashboard } = useWorkspaceDashboard();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteDashboard(workspaceSlug, dashboard.id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("dashboards.toast.deleted") });
      onClose();
      if (redirectOnDelete) router.push(`/${workspaceSlug}/dashboards`);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") });
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
      title={t("dashboards.delete.title")}
      content={<>{t("dashboards.delete.description", { name: dashboard.name })}</>}
      primaryButtonText={{ loading: t("dashboards.delete.deleting"), default: t("dashboards.delete.confirm") }}
      secondaryButtonText={t("cancel")}
    />
  );
});
