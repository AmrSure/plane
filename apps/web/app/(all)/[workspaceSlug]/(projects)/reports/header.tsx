/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams, usePathname } from "next/navigation";
import { FileChartColumn, Plus } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";

export const WorkspaceReportsHeader = observer(function WorkspaceReportsHeader() {
  const { workspaceSlug, reportId } = useParams();
  const pathname = usePathname();
  const router = useAppRouter();
  const { t } = useTranslation();
  const { getReportById } = useWorkspaceReport();
  const { allowPermissions } = useUserPermissions();
  const slug = workspaceSlug?.toString() ?? "";
  const isNew = pathname.includes("/reports/new");
  const report = reportId ? getReportById(reportId.toString()) : undefined;
  const isList = !reportId && !isNew;
  const canCreate = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("reports.label")}
                href={isList ? undefined : `/${slug}/reports`}
                icon={<FileChartColumn className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          {!isList && (
            <Breadcrumbs.Item
              component={<BreadcrumbLink label={report?.name ?? t("reports.builder.new_title")} isLast />}
            />
          )}
        </Breadcrumbs>
      </Header.LeftItem>
      <Header.RightItem>
        {isList && canCreate && (
          <Button
            variant="primary"
            size="lg"
            prependIcon={<Plus className="size-3.5" />}
            onClick={() => router.push(`/${slug}/reports/new`)}
          >
            {t("reports.list.new")}
          </Button>
        )}
      </Header.RightItem>
    </Header>
  );
});
