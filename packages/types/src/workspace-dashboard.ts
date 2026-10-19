/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TReportAccess, TReportDateRange, TReportDisplay, TReportQueryConfig } from "./reports";

export type TDashboardWidgetType = "number" | "bar" | "stacked_bar" | "line" | "area" | "pie" | "donut" | "table";

export type TDashboardWidgetSize = "small" | "medium" | "large" | "full";

export type TDashboardFilters = {
  project_ids?: string[];
  date_range?: TReportDateRange | null;
};

export type TWorkspaceDashboard = {
  id: string;
  workspace: string;
  name: string;
  description: string;
  logo_props: Record<string, unknown>;
  access: TReportAccess;
  owned_by: string;
  sort_order: number;
  filters: TDashboardFilters;
  widget_count?: number;
  is_owner: boolean;
  created_at: string;
  updated_at: string;
};

export type TDashboardWidget = {
  id: string;
  dashboard: string;
  name: string;
  widget_type: TDashboardWidgetType;
  size: TDashboardWidgetSize;
  sort_order: number;
  config: TReportQueryConfig;
  display: TReportDisplay;
  created_at: string;
  updated_at: string;
};

export type TWorkspaceDashboardDetail = TWorkspaceDashboard & { widgets: TDashboardWidget[] };

export type TWorkspaceDashboardFormData = Pick<TWorkspaceDashboard, "name" | "description" | "access">;

export type TDashboardWidgetFormData = Pick<TDashboardWidget, "name" | "widget_type" | "size" | "config" | "display">;
