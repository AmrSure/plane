/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
// components
import { PageHead } from "@/components/core/page-title";
import { ReportBuilder } from "@/components/reports";
// hooks
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";
import { useUserPermissions } from "@/hooks/store/user";
import type { Route } from "./+types/page";

function SavedReportPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, reportId } = params;
  const { t } = useTranslation();
  const { getReportById } = useWorkspaceReport();
  const { allowPermissions } = useUserPermissions();
  const canAccess = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  if (!canAccess) {
    return (
      <EmptyStateDetailed
        assetKey="no-access"
        title={t("dashboards.restricted.title")}
        description={t("dashboards.restricted.description")}
      />
    );
  }

  return (
    <>
      <PageHead title={getReportById(reportId)?.name} />
      <ReportBuilder key={reportId} workspaceSlug={workspaceSlug} reportId={reportId} />
    </>
  );
}

export default observer(SavedReportPage);
