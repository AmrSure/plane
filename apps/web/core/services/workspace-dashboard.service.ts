/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TDashboardWidget,
  TDashboardWidgetFormData,
  TDashboardWidgetSize,
  TDashboardWidgetType,
  TReportQueryConfig,
  TReportWidgetResult,
  TWorkspaceDashboard,
  TWorkspaceDashboardDetail,
} from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class WorkspaceDashboardService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/dashboards`;
  }

  async list(workspaceSlug: string): Promise<TWorkspaceDashboard[]> {
    return this.get(`${this.base(workspaceSlug)}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async retrieve(workspaceSlug: string, dashboardId: string): Promise<TWorkspaceDashboardDetail> {
    return this.get(`${this.base(workspaceSlug)}/${dashboardId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: Partial<TWorkspaceDashboard>): Promise<TWorkspaceDashboard> {
    return this.post(`${this.base(workspaceSlug)}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    dashboardId: string,
    data: Partial<TWorkspaceDashboard>
  ): Promise<TWorkspaceDashboard> {
    return this.patch(`${this.base(workspaceSlug)}/${dashboardId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroy(workspaceSlug: string, dashboardId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}/${dashboardId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWidget(
    workspaceSlug: string,
    dashboardId: string,
    data: Partial<TDashboardWidgetFormData>
  ): Promise<TDashboardWidget> {
    return this.post(`${this.base(workspaceSlug)}/${dashboardId}/widgets/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWidget(
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    data: Partial<TDashboardWidgetFormData>
  ): Promise<TDashboardWidget> {
    return this.patch(`${this.base(workspaceSlug)}/${dashboardId}/widgets/${widgetId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWidget(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}/${dashboardId}/widgets/${widgetId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async reorderWidgets(
    workspaceSlug: string,
    dashboardId: string,
    widgets: { id: string; sort_order?: number; size?: TDashboardWidgetSize }[]
  ): Promise<TDashboardWidget[]> {
    return this.post(`${this.base(workspaceSlug)}/${dashboardId}/widgets/reorder/`, { widgets })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWidgetData(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<TReportWidgetResult> {
    return this.get(`${this.base(workspaceSlug)}/${dashboardId}/widgets/${widgetId}/data/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async previewWidget(
    workspaceSlug: string,
    widgetType: TDashboardWidgetType,
    config: TReportQueryConfig
  ): Promise<TReportWidgetResult> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboard-widgets/preview/`, {
      widget_type: widgetType,
      config,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
