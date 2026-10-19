/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set, unset } from "lodash-es";
import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type {
  TDashboardWidget,
  TDashboardWidgetFormData,
  TDashboardWidgetSize,
  TWorkspaceDashboard,
} from "@plane/types";
// services
import { WorkspaceDashboardService } from "@/services/workspace-dashboard.service";
// store
import type { CoreRootStore } from "./root.store";

export interface IWorkspaceDashboardStore {
  // observables
  dashboardMap: Record<string, TWorkspaceDashboard>;
  widgetMap: Record<string, Record<string, TDashboardWidget>>;
  fetchedWorkspaces: Set<string>;
  // computed
  currentWorkspaceDashboardIds: string[] | undefined;
  // computed actions
  getDashboardById: (dashboardId: string) => TWorkspaceDashboard | undefined;
  getSortedWidgets: (dashboardId: string) => TDashboardWidget[];
  // actions
  fetchDashboards: (workspaceSlug: string) => Promise<TWorkspaceDashboard[]>;
  fetchDashboardDetails: (workspaceSlug: string, dashboardId: string) => Promise<TWorkspaceDashboard>;
  createDashboard: (workspaceSlug: string, data: Partial<TWorkspaceDashboard>) => Promise<TWorkspaceDashboard>;
  updateDashboard: (
    workspaceSlug: string,
    dashboardId: string,
    data: Partial<TWorkspaceDashboard>
  ) => Promise<TWorkspaceDashboard>;
  deleteDashboard: (workspaceSlug: string, dashboardId: string) => Promise<void>;
  createWidget: (
    workspaceSlug: string,
    dashboardId: string,
    data: Partial<TDashboardWidgetFormData>
  ) => Promise<TDashboardWidget>;
  updateWidget: (
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    data: Partial<TDashboardWidgetFormData>
  ) => Promise<TDashboardWidget>;
  deleteWidget: (workspaceSlug: string, dashboardId: string, widgetId: string) => Promise<void>;
  moveWidget: (
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    targetWidgetId: string,
    edge: "left" | "right"
  ) => Promise<void>;
  resizeWidget: (
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    size: TDashboardWidgetSize
  ) => Promise<void>;
}

export class WorkspaceDashboardStore implements IWorkspaceDashboardStore {
  dashboardMap: Record<string, TWorkspaceDashboard> = {};
  widgetMap: Record<string, Record<string, TDashboardWidget>> = {};
  fetchedWorkspaces: Set<string> = new Set();
  rootStore;
  service;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      dashboardMap: observable,
      widgetMap: observable,
      fetchedWorkspaces: observable,
      currentWorkspaceDashboardIds: computed,
      fetchDashboards: action,
      fetchDashboardDetails: action,
      createDashboard: action,
      updateDashboard: action,
      deleteDashboard: action,
      createWidget: action,
      updateWidget: action,
      deleteWidget: action,
      moveWidget: action,
      resizeWidget: action,
    });
    this.rootStore = _rootStore;
    this.service = new WorkspaceDashboardService();
  }

  get currentWorkspaceDashboardIds() {
    const workspace = this.rootStore.workspaceRoot.currentWorkspace;
    if (!workspace || !this.fetchedWorkspaces.has(workspace.slug)) return undefined;
    return Object.values(this.dashboardMap)
      .filter((dashboard) => dashboard.workspace === workspace.id)
      .sort((a, b) => a.sort_order - b.sort_order || b.created_at.localeCompare(a.created_at))
      .map((dashboard) => dashboard.id);
  }

  getDashboardById = computedFn((dashboardId: string) => this.dashboardMap[dashboardId]);

  getSortedWidgets = computedFn((dashboardId: string) =>
    Object.values(this.widgetMap[dashboardId] ?? {}).sort(
      (a, b) => a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at)
    )
  );

  fetchDashboards = async (workspaceSlug: string) => {
    const dashboards = await this.service.list(workspaceSlug);
    runInAction(() => {
      dashboards.forEach((dashboard) => set(this.dashboardMap, [dashboard.id], dashboard));
      this.fetchedWorkspaces.add(workspaceSlug);
    });
    return dashboards;
  };

  fetchDashboardDetails = async (workspaceSlug: string, dashboardId: string) => {
    const { widgets, ...dashboard } = await this.service.retrieve(workspaceSlug, dashboardId);
    runInAction(() => {
      set(this.dashboardMap, [dashboard.id], { ...this.dashboardMap[dashboard.id], ...dashboard });
      this.widgetMap[dashboard.id] = Object.fromEntries(widgets.map((widget) => [widget.id, widget]));
    });
    return dashboard;
  };

  createDashboard = async (workspaceSlug: string, data: Partial<TWorkspaceDashboard>) => {
    const dashboard = await this.service.create(workspaceSlug, data);
    runInAction(() => {
      set(this.dashboardMap, [dashboard.id], { ...dashboard, widget_count: 0 });
      this.widgetMap[dashboard.id] = {};
    });
    return dashboard;
  };

  updateDashboard = async (workspaceSlug: string, dashboardId: string, data: Partial<TWorkspaceDashboard>) => {
    const dashboard = await this.service.update(workspaceSlug, dashboardId, data);
    runInAction(() => {
      set(this.dashboardMap, [dashboardId], { ...this.dashboardMap[dashboardId], ...dashboard });
    });
    return dashboard;
  };

  deleteDashboard = async (workspaceSlug: string, dashboardId: string) => {
    await this.service.destroy(workspaceSlug, dashboardId);
    runInAction(() => {
      unset(this.dashboardMap, [dashboardId]);
      unset(this.widgetMap, [dashboardId]);
    });
  };

  private bumpWidgetCount(dashboardId: string, delta: number) {
    const dashboard = this.dashboardMap[dashboardId];
    if (dashboard) set(this.dashboardMap, [dashboardId, "widget_count"], (dashboard.widget_count ?? 0) + delta);
  }

  createWidget = async (workspaceSlug: string, dashboardId: string, data: Partial<TDashboardWidgetFormData>) => {
    const widget = await this.service.createWidget(workspaceSlug, dashboardId, data);
    runInAction(() => {
      set(this.widgetMap, [dashboardId, widget.id], widget);
      this.bumpWidgetCount(dashboardId, 1);
    });
    return widget;
  };

  updateWidget = async (
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    data: Partial<TDashboardWidgetFormData>
  ) => {
    const widget = await this.service.updateWidget(workspaceSlug, dashboardId, widgetId, data);
    runInAction(() => set(this.widgetMap, [dashboardId, widgetId], widget));
    return widget;
  };

  deleteWidget = async (workspaceSlug: string, dashboardId: string, widgetId: string) => {
    await this.service.deleteWidget(workspaceSlug, dashboardId, widgetId);
    runInAction(() => {
      unset(this.widgetMap, [dashboardId, widgetId]);
      this.bumpWidgetCount(dashboardId, -1);
    });
  };

  moveWidget = async (
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    targetWidgetId: string,
    edge: "left" | "right"
  ) => {
    if (widgetId === targetWidgetId) return;
    const ordered = this.getSortedWidgets(dashboardId).filter((widget) => widget.id !== widgetId);
    const targetIndex = ordered.findIndex((widget) => widget.id === targetWidgetId);
    if (targetIndex < 0) return;
    const insertAt = edge === "left" ? targetIndex : targetIndex + 1;
    const before = ordered[insertAt - 1]?.sort_order;
    const after = ordered[insertAt]?.sort_order;
    let sortOrder: number;
    if (before === undefined && after === undefined) sortOrder = 65535;
    else if (before === undefined) sortOrder = (after as number) - 10000;
    else if (after === undefined) sortOrder = before + 10000;
    else sortOrder = (before + after) / 2;

    const previous = this.widgetMap[dashboardId]?.[widgetId]?.sort_order;
    runInAction(() => set(this.widgetMap, [dashboardId, widgetId, "sort_order"], sortOrder));
    try {
      await this.service.reorderWidgets(workspaceSlug, dashboardId, [{ id: widgetId, sort_order: sortOrder }]);
    } catch (error) {
      runInAction(() => set(this.widgetMap, [dashboardId, widgetId, "sort_order"], previous));
      throw error;
    }
  };

  resizeWidget = async (workspaceSlug: string, dashboardId: string, widgetId: string, size: TDashboardWidgetSize) => {
    const previous = this.widgetMap[dashboardId]?.[widgetId]?.size;
    runInAction(() => set(this.widgetMap, [dashboardId, widgetId, "size"], size));
    try {
      await this.service.reorderWidgets(workspaceSlug, dashboardId, [{ id: widgetId, size }]);
    } catch (error) {
      runInAction(() => set(this.widgetMap, [dashboardId, widgetId, "size"], previous));
      throw error;
    }
  };
}
