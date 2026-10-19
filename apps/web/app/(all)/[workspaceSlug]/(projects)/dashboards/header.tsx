/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Check, LayoutGrid, Link2, Plus } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { DashboardIcon, EditIcon, TrashIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Breadcrumbs, CustomMenu, Header } from "@plane/ui";
import { copyUrlToClipboard } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CreateUpdateDashboardModal, DeleteDashboardModal, useDashboardPage } from "@/components/workspace-dashboards";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { useUserPermissions } from "@/hooks/store/user";

export const WorkspaceDashboardsHeader = observer(function WorkspaceDashboardsHeader() {
  const { workspaceSlug, dashboardId } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { t } = useTranslation();
  const { getDashboardById } = useWorkspaceDashboard();
  const { allowPermissions } = useUserPermissions();
  const { isCreateOpen, setIsCreateOpen, setIsWidgetEditorOpen, isEditingLayout, setIsEditingLayout } =
    useDashboardPage();
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const canCreate = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );
  const dashboard = dashboardId ? getDashboardById(dashboardId.toString()) : undefined;

  const handleCopyLink = () =>
    copyUrlToClipboard(`${slug}/dashboards/${dashboard?.id}`).then(() =>
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("dashboards.toast.link_copied") })
    );

  return (
    <>
      <CreateUpdateDashboardModal workspaceSlug={slug} isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
      {dashboard && (
        <>
          <CreateUpdateDashboardModal
            workspaceSlug={slug}
            isOpen={isEditOpen}
            onClose={() => setIsEditOpen(false)}
            data={dashboard}
          />
          <DeleteDashboardModal
            workspaceSlug={slug}
            dashboard={dashboard}
            isOpen={isDeleteOpen}
            onClose={() => setIsDeleteOpen(false)}
            redirectOnDelete
          />
        </>
      )}
      <Header>
        <Header.LeftItem>
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label={t("dashboards.label")}
                  href={dashboardId ? `/${slug}/dashboards` : undefined}
                  icon={<DashboardIcon className="h-4 w-4 text-tertiary" />}
                />
              }
            />
            {dashboard && <Breadcrumbs.Item component={<BreadcrumbLink label={dashboard.name} isLast />} />}
          </Breadcrumbs>
        </Header.LeftItem>
        <Header.RightItem>
          {!dashboardId && canCreate && (
            <Button
              variant="primary"
              size="lg"
              prependIcon={<Plus className="size-3.5" />}
              onClick={() => setIsCreateOpen(true)}
            >
              {t("dashboards.list.new")}
            </Button>
          )}
          {dashboard?.is_owner && (
            <div className="flex items-center gap-2">
              <Button
                variant={isEditingLayout ? "primary" : "secondary"}
                size="lg"
                prependIcon={isEditingLayout ? <Check className="size-3.5" /> : <LayoutGrid className="size-3.5" />}
                onClick={() => setIsEditingLayout(!isEditingLayout)}
              >
                {isEditingLayout ? t("dashboards.actions.done") : t("dashboards.actions.edit_layout")}
              </Button>
              <Button
                variant="primary"
                size="lg"
                prependIcon={<Plus className="size-3.5" />}
                onClick={() => setIsWidgetEditorOpen(true)}
              >
                {t("dashboards.actions.add_widget")}
              </Button>
            </div>
          )}
          {dashboard && (
            <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
              <CustomMenu.MenuItem onClick={handleCopyLink}>
                <span className="flex items-center gap-2">
                  <Link2 className="size-3.5" />
                  {t("dashboards.actions.copy_link")}
                </span>
              </CustomMenu.MenuItem>
              {dashboard.is_owner && (
                <CustomMenu.MenuItem onClick={() => setIsEditOpen(true)}>
                  <span className="flex items-center gap-2">
                    <EditIcon width={14} height={14} />
                    {t("dashboards.actions.edit")}
                  </span>
                </CustomMenu.MenuItem>
              )}
              {dashboard.is_owner && (
                <CustomMenu.MenuItem onClick={() => setIsDeleteOpen(true)}>
                  <span className="flex items-center gap-2 text-danger-primary">
                    <TrashIcon width={14} height={14} />
                    {t("dashboards.actions.delete")}
                  </span>
                </CustomMenu.MenuItem>
              )}
            </CustomMenu>
          )}
        </Header.RightItem>
      </Header>
    </>
  );
});
