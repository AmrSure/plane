/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
import { Globe, Lock, Search } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { DashboardIcon, EditIcon, TrashIcon } from "@plane/propel/icons";
import type { TWorkspaceDashboard } from "@plane/types";
import { CustomMenu, Loader } from "@plane/ui";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
// local imports
import { CreateUpdateDashboardModal } from "../modals/create-update-dashboard-modal";
import { DeleteDashboardModal } from "../modals/delete-dashboard-modal";

type Props = {
  workspaceSlug: string;
  onCreate: () => void;
};

const DashboardListItem = observer(function DashboardListItem(props: {
  workspaceSlug: string;
  dashboard: TWorkspaceDashboard;
}) {
  const { workspaceSlug, dashboard } = props;
  const { t } = useTranslation();
  const { getUserDetails } = useMember();
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const owner = getUserDetails(dashboard.owned_by);

  return (
    <>
      <CreateUpdateDashboardModal
        workspaceSlug={workspaceSlug}
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        data={dashboard}
      />
      <DeleteDashboardModal
        workspaceSlug={workspaceSlug}
        dashboard={dashboard}
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
      />
      <div className="group flex items-center gap-3 border-b border-subtle px-6 py-3 hover:bg-layer-1">
        <DashboardIcon className="size-4 flex-shrink-0 text-tertiary" />
        <Link href={`/${workspaceSlug}/dashboards/${dashboard.id}`} className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-14 font-medium text-primary">{dashboard.name}</span>
          {dashboard.description && <span className="truncate text-12 text-tertiary">{dashboard.description}</span>}
        </Link>
        <span className="hidden text-12 text-tertiary sm:block">
          {t("dashboards.list.widget_count", { count: dashboard.widget_count ?? 0 })}
        </span>
        <span className="hidden items-center gap-1 text-12 text-tertiary md:flex">
          {dashboard.access === 1 ? <Globe className="size-3.5" /> : <Lock className="size-3.5" />}
          {dashboard.access === 1 ? t("dashboards.access.workspace") : t("dashboards.access.private")}
        </span>
        <span className="hidden w-32 truncate text-right text-12 text-tertiary lg:block">
          {dashboard.is_owner ? t("dashboards.list.owned_by_you") : (owner?.display_name ?? "")}
        </span>
        <span className="hidden w-24 text-right text-12 text-tertiary lg:block">
          {renderFormattedDate(dashboard.updated_at)}
        </span>
        {dashboard.is_owner && (
          <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
            <CustomMenu.MenuItem onClick={() => setIsEditOpen(true)}>
              <span className="flex items-center gap-2">
                <EditIcon width={14} height={14} />
                {t("dashboards.actions.edit")}
              </span>
            </CustomMenu.MenuItem>
            <CustomMenu.MenuItem onClick={() => setIsDeleteOpen(true)}>
              <span className="flex items-center gap-2 text-danger-primary">
                <TrashIcon width={14} height={14} />
                {t("dashboards.actions.delete")}
              </span>
            </CustomMenu.MenuItem>
          </CustomMenu>
        )}
      </div>
    </>
  );
});

export const WorkspaceDashboardList = observer(function WorkspaceDashboardList(props: Props) {
  const { workspaceSlug, onCreate } = props;
  const { t } = useTranslation();
  const { fetchDashboards, currentWorkspaceDashboardIds, getDashboardById } = useWorkspaceDashboard();
  const [search, setSearch] = useState("");

  useSWR(`WORKSPACE_DASHBOARDS_${workspaceSlug}`, () => fetchDashboards(workspaceSlug), {
    revalidateOnFocus: false,
  });

  if (!currentWorkspaceDashboardIds) {
    return (
      <Loader className="space-y-2 p-6">
        {[1, 2, 3].map((item) => (
          <Loader.Item key={item} height="48px" />
        ))}
      </Loader>
    );
  }

  if (currentWorkspaceDashboardIds.length === 0) {
    return (
      <EmptyStateDetailed
        assetKey="dashboard"
        title={t("dashboards.list.empty.title")}
        description={t("dashboards.list.empty.description")}
        actions={[{ label: t("dashboards.list.empty.cta"), onClick: onCreate, variant: "primary" }]}
      />
    );
  }

  const query = search.trim().toLowerCase();
  const dashboards = currentWorkspaceDashboardIds
    .map((id) => getDashboardById(id))
    .filter((dashboard): dashboard is TWorkspaceDashboard => Boolean(dashboard))
    .filter((dashboard) => !query || dashboard.name.toLowerCase().includes(query));

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex items-center gap-2 border-b border-subtle px-6 py-2.5">
        <Search className="size-3.5 text-tertiary" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("dashboards.list.search_placeholder")}
          className="w-full bg-transparent text-13 text-primary outline-none placeholder:text-placeholder"
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {dashboards.length === 0 ? (
          <p className="p-6 text-13 text-tertiary">{t("dashboards.list.no_results")}</p>
        ) : (
          dashboards.map((dashboard) => (
            <DashboardListItem key={dashboard.id} workspaceSlug={workspaceSlug} dashboard={dashboard} />
          ))
        )}
      </div>
    </div>
  );
});
