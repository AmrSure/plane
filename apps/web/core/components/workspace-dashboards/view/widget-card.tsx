/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { attachClosestEdge, extractClosestEdge } from "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Copy, GripVertical, Info, Maximize2, Pencil, Trash2 } from "lucide-react";
// plane imports
import { DASHBOARD_WIDGET_SIZES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import type { TDashboardWidget, TDashboardWidgetSize } from "@plane/types";
import { AlertModalCore, CustomMenu } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { ReportChartError, ReportChartLoader, ReportResultView } from "@/components/report-charts";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { WorkspaceDashboardService } from "@/services/workspace-dashboard.service";

const dashboardService = new WorkspaceDashboardService();

const WIDGET_HEIGHT: Record<string, string> = {
  number: "h-[11rem]",
  table: "h-[24rem]",
};

type Props = {
  workspaceSlug: string;
  dashboardId: string;
  widget: TDashboardWidget;
  isOwner: boolean;
  isEditingLayout: boolean;
  onEdit: (widget: TDashboardWidget) => void;
};

export const DashboardWidgetCard = observer(function DashboardWidgetCard(props: Props) {
  const { workspaceSlug, dashboardId, widget, isOwner, isEditingLayout, onEdit } = props;
  const { t } = useTranslation();
  const { deleteWidget, createWidget, moveWidget, resizeWidget } = useWorkspaceDashboard();
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [dropEdge, setDropEdge] = useState<"left" | "right" | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HTMLButtonElement>(null);

  const { data, error, isLoading, mutate } = useSWR(
    `DASHBOARD_WIDGET_DATA_${widget.id}_${widget.updated_at}`,
    () => dashboardService.getWidgetData(workspaceSlug, dashboardId, widget.id),
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    const element = cardRef.current;
    const handle = handleRef.current;
    if (!element || !handle || !isEditingLayout) return;
    return combine(
      draggable({
        element,
        dragHandle: handle,
        getInitialData: () => ({ widgetId: widget.id, dashboardId }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) => source.data.dashboardId === dashboardId && source.data.widgetId !== widget.id,
        getData: ({ input, element: target }) =>
          attachClosestEdge({ widgetId: widget.id }, { input, element: target, allowedEdges: ["left", "right"] }),
        onDrag: ({ self }) => setDropEdge(extractClosestEdge(self.data) as "left" | "right" | null),
        onDragLeave: () => setDropEdge(null),
        onDrop: ({ self, source }) => {
          const edge = extractClosestEdge(self.data) as "left" | "right" | null;
          setDropEdge(null);
          if (!edge) return;
          moveWidget(workspaceSlug, dashboardId, String(source.data.widgetId), widget.id, edge).catch(() =>
            setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") })
          );
        },
      })
    );
  }, [dashboardId, isEditingLayout, moveWidget, t, widget.id, workspaceSlug]);

  const handleResize = (size: TDashboardWidgetSize) =>
    resizeWidget(workspaceSlug, dashboardId, widget.id, size).catch(() =>
      setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") })
    );

  const handleDuplicate = () =>
    createWidget(workspaceSlug, dashboardId, {
      name: widget.name,
      widget_type: widget.widget_type,
      size: widget.size,
      config: widget.config,
      display: widget.display,
    }).catch(() => setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") }));

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteWidget(workspaceSlug, dashboardId, widget.id);
      setIsDeleteOpen(false);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") });
    } finally {
      setIsDeleting(false);
    }
  };

  const sizeClass = DASHBOARD_WIDGET_SIZES.find((s) => s.key === widget.size)?.className ?? "col-span-1";
  const title = widget.name || t("dashboards.widget.untitled");

  return (
    <>
      <AlertModalCore
        isOpen={isDeleteOpen}
        handleClose={() => setIsDeleteOpen(false)}
        handleSubmit={handleDelete}
        isSubmitting={isDeleting}
        title={t("dashboards.widget.delete.title")}
        content={<>{t("dashboards.widget.delete.description", { name: title })}</>}
        primaryButtonText={{ loading: t("dashboards.delete.deleting"), default: t("dashboards.delete.confirm") }}
        secondaryButtonText={t("cancel")}
      />
      <div
        ref={cardRef}
        className={cn(
          "relative flex flex-col rounded-lg border border-subtle bg-surface-1 p-4 transition-shadow",
          sizeClass,
          WIDGET_HEIGHT[widget.widget_type] ?? "h-[20rem]",
          { "opacity-50": isDragging, "ring-1 ring-accent-strong": isEditingLayout }
        )}
      >
        {dropEdge && (
          <span
            className={cn("absolute top-2 bottom-2 w-0.5 rounded-full bg-accent-primary", {
              "-left-2": dropEdge === "left",
              "-right-2": dropEdge === "right",
            })}
          />
        )}
        <div className="mb-2 flex items-center gap-2">
          {isEditingLayout && (
            <button
              ref={handleRef}
              type="button"
              className="flex-shrink-0 cursor-grab text-tertiary hover:text-secondary"
              aria-label={t("dashboards.actions.edit_layout")}
            >
              <GripVertical className="size-4" />
            </button>
          )}
          <h4 className="line-clamp-1 flex-1 text-14 font-medium text-primary" title={title}>
            {title}
          </h4>
          {!isOwner && (
            <Tooltip tooltipContent={t("dashboards.widget.scope_hint")}>
              <Info className="size-3.5 flex-shrink-0 text-tertiary" />
            </Tooltip>
          )}
          {isOwner && (
            <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
              <CustomMenu.MenuItem onClick={() => onEdit(widget)}>
                <span className="flex items-center gap-2">
                  <Pencil className="size-3.5" />
                  {t("dashboards.widget.actions.edit")}
                </span>
              </CustomMenu.MenuItem>
              <CustomMenu.MenuItem onClick={handleDuplicate}>
                <span className="flex items-center gap-2">
                  <Copy className="size-3.5" />
                  {t("dashboards.widget.actions.duplicate")}
                </span>
              </CustomMenu.MenuItem>
              {DASHBOARD_WIDGET_SIZES.map((size) => (
                <CustomMenu.MenuItem key={size.key} onClick={() => handleResize(size.key)}>
                  <span
                    className={cn("flex items-center gap-2", {
                      "font-medium text-accent-primary": widget.size === size.key,
                    })}
                  >
                    <Maximize2 className="size-3.5" />
                    {t(size.i18n_label)}
                  </span>
                </CustomMenu.MenuItem>
              ))}
              <CustomMenu.MenuItem onClick={() => setIsDeleteOpen(true)}>
                <span className="flex items-center gap-2 text-danger-primary">
                  <Trash2 className="size-3.5" />
                  {t("dashboards.widget.actions.delete")}
                </span>
              </CustomMenu.MenuItem>
            </CustomMenu>
          )}
        </div>
        <div className="min-h-0 flex-1">
          {isLoading ? (
            <ReportChartLoader />
          ) : error ? (
            <ReportChartError error={error} onRetry={() => mutate()} />
          ) : data ? (
            <ReportResultView
              workspaceSlug={workspaceSlug}
              widgetType={widget.widget_type}
              result={data}
              config={widget.config}
              display={widget.display}
            />
          ) : null}
        </div>
        {data && data.meta?.truncated && data.kind === "chart" && (
          <p className="mt-1 text-11 text-tertiary">{t("dashboards.widget.states.truncated")}</p>
        )}
      </div>
    </>
  );
});
