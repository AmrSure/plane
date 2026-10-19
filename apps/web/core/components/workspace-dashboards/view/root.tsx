/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import type { TDashboardWidget } from "@plane/types";
import { Loader } from "@plane/ui";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
// local imports
import { DashboardWidgetEditorModal } from "../widget-editor/modal";
import { DashboardWidgetCard } from "./widget-card";

type Props = {
  workspaceSlug: string;
  dashboardId: string;
  isEditingLayout: boolean;
  isWidgetEditorOpen: boolean;
  onWidgetEditorClose: () => void;
  onAddWidget: () => void;
};

export const WorkspaceDashboardView = observer(function WorkspaceDashboardView(props: Props) {
  const { workspaceSlug, dashboardId, isEditingLayout, isWidgetEditorOpen, onWidgetEditorClose, onAddWidget } = props;
  const { t } = useTranslation();
  const { fetchDashboardDetails, getDashboardById, getSortedWidgets } = useWorkspaceDashboard();
  const [editingWidget, setEditingWidget] = useState<TDashboardWidget | undefined>();

  const { isLoading, error } = useSWR(
    `WORKSPACE_DASHBOARD_${workspaceSlug}_${dashboardId}`,
    () => fetchDashboardDetails(workspaceSlug, dashboardId),
    { revalidateOnFocus: false }
  );

  const dashboard = getDashboardById(dashboardId);
  const widgets = getSortedWidgets(dashboardId);

  if (error && !dashboard) {
    return (
      <EmptyStateDetailed
        assetKey="invalid-link"
        title={t("dashboards.not_found.title")}
        description={t("dashboards.not_found.description")}
      />
    );
  }

  if (isLoading && !widgets.length) {
    return (
      <Loader className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <Loader.Item key={item} height="18rem" className="md:col-span-2" />
        ))}
      </Loader>
    );
  }

  const isOwner = Boolean(dashboard?.is_owner);
  const closeEditor = () => {
    setEditingWidget(undefined);
    onWidgetEditorClose();
  };

  return (
    <div className="h-full w-full overflow-y-auto">
      <DashboardWidgetEditorModal
        workspaceSlug={workspaceSlug}
        dashboardId={dashboardId}
        isOpen={isWidgetEditorOpen || Boolean(editingWidget)}
        onClose={closeEditor}
        widget={editingWidget}
      />
      {dashboard?.description && <p className="px-6 pt-4 text-13 text-secondary">{dashboard.description}</p>}
      {widgets.length === 0 ? (
        <EmptyStateDetailed
          assetKey="dashboard"
          title={t("dashboards.empty_widgets.title")}
          description={
            isOwner ? t("dashboards.empty_widgets.description") : t("dashboards.empty_widgets.viewer_description")
          }
          actions={
            isOwner ? [{ label: t("dashboards.actions.add_widget"), onClick: onAddWidget, variant: "primary" }] : []
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2 xl:grid-cols-4">
          {widgets.map((widget) => (
            <DashboardWidgetCard
              key={widget.id}
              workspaceSlug={workspaceSlug}
              dashboardId={dashboardId}
              widget={widget}
              isOwner={isOwner}
              isEditingLayout={isOwner && isEditingLayout}
              onEdit={setEditingWidget}
            />
          ))}
        </div>
      )}
    </div>
  );
});
