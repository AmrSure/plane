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
import { WorkspaceDashboardList, useDashboardPage } from "@/components/workspace-dashboards";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
import type { Route } from "./+types/page";

function WorkspaceDashboardsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { t } = useTranslation();
  const { currentWorkspace } = useWorkspace();
  const { allowPermissions } = useUserPermissions();
  const { setIsCreateOpen } = useDashboardPage();
  const canAccess = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );
  const pageTitle = currentWorkspace?.name
    ? t("dashboards.page_title", { workspace: currentWorkspace.name })
    : undefined;

  return (
    <>
      <PageHead title={pageTitle} />
      {canAccess ? (
        <WorkspaceDashboardList workspaceSlug={workspaceSlug} onCreate={() => setIsCreateOpen(true)} />
      ) : (
        <EmptyStateDetailed
          assetKey="no-access"
          title={t("dashboards.restricted.title")}
          description={t("dashboards.restricted.description")}
        />
      )}
    </>
  );
}

export default observer(WorkspaceDashboardsPage);
