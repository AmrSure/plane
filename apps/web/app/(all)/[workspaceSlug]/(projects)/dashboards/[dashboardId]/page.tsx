/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
// components
import { PageHead } from "@/components/core/page-title";
import { WorkspaceDashboardView, useDashboardPage } from "@/components/workspace-dashboards";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { useUserPermissions } from "@/hooks/store/user";
import type { Route } from "./+types/page";

function WorkspaceDashboardDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, dashboardId } = params;
  const { t } = useTranslation();
  const { getDashboardById } = useWorkspaceDashboard();
  const { allowPermissions } = useUserPermissions();
  const { isWidgetEditorOpen, setIsWidgetEditorOpen, isEditingLayout, setIsEditingLayout } = useDashboardPage();
  const canAccess = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );
  const dashboard = getDashboardById(dashboardId);

  // Leave layout editing when switching dashboards
  useEffect(() => setIsEditingLayout(false), [dashboardId, setIsEditingLayout]);

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
      <PageHead title={dashboard?.name} />
      <WorkspaceDashboardView
        workspaceSlug={workspaceSlug}
        dashboardId={dashboardId}
        isEditingLayout={isEditingLayout}
        isWidgetEditorOpen={isWidgetEditorOpen}
        onWidgetEditorClose={() => setIsWidgetEditorOpen(false)}
        onAddWidget={() => setIsWidgetEditorOpen(true)}
      />
    </>
  );
}

export default observer(WorkspaceDashboardDetailPage);
