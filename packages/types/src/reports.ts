/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ChartXAxisProperty, ChartYAxisMetric } from "./analytics";

// ---------------------------------------------------------------- query config

export type TReportMetric = ChartYAxisMetric.WORK_ITEM_COUNT | ChartYAxisMetric.ESTIMATE_POINT_COUNT;

export type TReportDimension = Exclude<
  ChartXAxisProperty,
  ChartXAxisProperty.WORK_ITEM_TYPES | ChartXAxisProperty.EPICS
>;

export type TReportDateGrouping = "DAY" | "WEEK" | "MONTH" | "YEAR";

export type TReportDateField = "created_at" | "completed_at" | "start_date" | "target_date";

export type TReportDatePreset =
  | "last_7_days"
  | "last_30_days"
  | "last_90_days"
  | "this_month"
  | "last_month"
  | "this_quarter"
  | "this_year"
  | "custom";

export type TReportDateRange = {
  field: TReportDateField;
  preset?: TReportDatePreset | null;
  start?: string | null;
  end?: string | null;
};

export type TReportTableColumn =
  | "sequence_id"
  | "project_identifier"
  | "name"
  | "state_name"
  | "state_group"
  | "priority"
  | "assignees"
  | "labels"
  | "start_date"
  | "target_date"
  | "completed_at"
  | "created_at"
  | "estimate";

export type TReportTableOrderBy =
  | "created_at"
  | "-created_at"
  | "target_date"
  | "-target_date"
  | "completed_at"
  | "-completed_at"
  | "sequence_id"
  | "-sequence_id"
  | "name"
  | "-name";

export type TReportTableConfig = {
  columns?: TReportTableColumn[];
  order_by?: TReportTableOrderBy;
  limit?: number;
};

/** Rich filter expression: leaf conditions such as { "priority__in": "high,urgent" } combined with and/or/not. */
export type TReportFilterExpression = {
  and?: TReportFilterExpression[];
  or?: TReportFilterExpression[];
  not?: TReportFilterExpression;
  [condition: string]: unknown;
};

export type TReportQueryConfig = {
  metric: TReportMetric;
  x_axis?: TReportDimension | null;
  group_by?: TReportDimension | null;
  date_grouping?: TReportDateGrouping | null;
  project_ids?: string[];
  filters?: TReportFilterExpression;
  date_range?: TReportDateRange | null;
  include_sub_work_items?: boolean;
  table?: TReportTableConfig | null;
};

// ---------------------------------------------------------------- results

export type TReportResultMeta = {
  metric: TReportMetric;
  x_axis?: TReportDimension | null;
  group_by?: TReportDimension | null;
  date_grouping?: TReportDateGrouping | null;
  project_count: number;
  generated_at: string;
  truncated: boolean;
  columns?: TReportTableColumn[];
};

export type TReportChartDatum = {
  key: string;
  name: string;
  count: number;
  color?: string;
  [segment: string]: string | number | undefined;
};

export type TReportChartResult = {
  data: TReportChartDatum[];
  schema: Record<string, string>;
  totals: { value: number; work_item_count: number };
  meta: TReportResultMeta;
};

export type TReportNumberResult = {
  value: number;
  work_item_count: number;
  meta: TReportResultMeta;
};

export type TReportTableRow = {
  id: string;
  project_id: string;
  state_color?: string | null;
  sequence_id?: number;
  project_identifier?: string;
  name?: string;
  state_name?: string;
  state_group?: string;
  priority?: string;
  assignees?: string[];
  assignee_ids?: string[];
  labels?: string[];
  start_date?: string | null;
  target_date?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  estimate?: string | null;
};

export type TReportTableResult = {
  results: TReportTableRow[];
  total_count: number;
  meta: TReportResultMeta;
};

export type TReportWidgetResult =
  | ({ kind: "chart" } & TReportChartResult)
  | ({ kind: "number" } & TReportNumberResult)
  | ({ kind: "table" } & TReportTableResult);

export type TReportQueryResponse = {
  chart?: TReportChartResult;
  number?: TReportNumberResult;
  table?: TReportTableResult;
};

export type TReportExportFormat = "csv" | "xlsx";

export type TReportExportLabels = {
  dimension?: string;
  total?: string;
  values?: Record<string, string>;
  columns?: Record<string, string>;
  sheets?: Record<string, string>;
};

// ---------------------------------------------------------------- saved reports

export type TReportAccess = 0 | 1;

export type TReportChartType = "bar" | "stacked_bar" | "line" | "area" | "pie" | "donut" | "table";

export type TReportDisplay = {
  palette?: "modern" | "horizon" | "earthen";
  show_legend?: boolean;
  show_values?: boolean;
  chart_type?: TReportChartType;
};

export type TSavedReport = {
  id: string;
  workspace: string;
  name: string;
  description: string;
  access: TReportAccess;
  owned_by: string;
  report_type: "custom";
  config: TReportQueryConfig;
  display: TReportDisplay;
  sort_order: number;
  is_owner: boolean;
  created_at: string;
  updated_at: string;
};

// ---------------------------------------------------------------- cycle report

export type TCycleReportSection =
  | "summary"
  | "burndown"
  | "assignees"
  | "labels"
  | "state_groups"
  | "priorities"
  | "scope_changes"
  | "incomplete_items";

export type TCycleReportBreakdownRow = {
  id: string;
  name: string;
  color?: string | null;
  total: number;
  completed?: number;
  pending?: number;
  points_total?: number | null;
  points_completed?: number | null;
};

export type TCycleReportItem = {
  id: string;
  sequence_id: number;
  project_identifier: string;
  name: string;
  state_name: string | null;
  state_group: string | null;
  state_color: string | null;
  priority: string;
  target_date: string | null;
  estimate: string | null;
  assignees: string[];
};

export type TCycleReportScopeChange = {
  id: string;
  name: string | null;
  sequence_id: number | null;
  project_identifier: string | null;
  at: string;
};

export type TCycleReport = {
  cycle: {
    id: string;
    name: string;
    project_id: string;
    start_date: string;
    end_date: string;
    timezone: string;
    status: "upcoming" | "current" | "completed";
    source: "live" | "snapshot";
  };
  summary: {
    total: number;
    completed: number;
    cancelled: number;
    pending: number;
    completion_pct: number;
    state_groups: Record<string, number>;
    points: { total: number; completed: number; cancelled: number; pending: number; completion_pct: number } | null;
    days_total: number;
    days_elapsed: number;
    days_left: number;
  };
  burndown: {
    dates: string[];
    issues: Record<string, number | null>;
    points: Record<string, number | null> | null;
  };
  breakdown: {
    assignees: TCycleReportBreakdownRow[];
    labels: TCycleReportBreakdownRow[];
    state_groups: TCycleReportBreakdownRow[];
    priorities: TCycleReportBreakdownRow[];
  };
  scope_changes: {
    available: boolean;
    added: TCycleReportScopeChange[];
    removed: TCycleReportScopeChange[];
    net_change: number;
  };
  incomplete_items: { results: TCycleReportItem[]; total_count: number; truncated: boolean };
  transferred_items: TCycleReportItem[];
  meta: { generated_at: string; priorities_source: "live" };
};
