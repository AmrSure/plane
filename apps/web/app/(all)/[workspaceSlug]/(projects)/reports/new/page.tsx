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
import { useUserPermissions } from "@/hooks/store/user";
import type { Route } from "./+types/page";

function NewReportPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { t } = useTranslation();
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
      <PageHead title={t("reports.builder.new_title")} />
      <ReportBuilder workspaceSlug={workspaceSlug} />
    </>
  );
}

export default observer(NewReportPage);
