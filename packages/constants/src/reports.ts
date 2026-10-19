/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TDashboardWidgetSize,
  TDashboardWidgetType,
  TReportChartType,
  TReportDateField,
  TReportDateGrouping,
  TReportDatePreset,
  TReportDimension,
  TReportMetric,
  TReportQueryConfig,
  TReportTableColumn,
} from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";

export const REPORT_DIMENSIONS: { key: TReportDimension; i18n_label: string; is_date?: boolean }[] = [
  { key: ChartXAxisProperty.STATES, i18n_label: "reports.dimensions.states" },
  { key: ChartXAxisProperty.STATE_GROUPS, i18n_label: "reports.dimensions.state_groups" },
  { key: ChartXAxisProperty.PRIORITY, i18n_label: "reports.dimensions.priority" },
  { key: ChartXAxisProperty.ASSIGNEES, i18n_label: "reports.dimensions.assignees" },
  { key: ChartXAxisProperty.LABELS, i18n_label: "reports.dimensions.labels" },
  { key: ChartXAxisProperty.PROJECTS, i18n_label: "reports.dimensions.projects" },
  { key: ChartXAxisProperty.CYCLES, i18n_label: "reports.dimensions.cycles" },
  { key: ChartXAxisProperty.MODULES, i18n_label: "reports.dimensions.modules" },
  { key: ChartXAxisProperty.ESTIMATE_POINTS, i18n_label: "reports.dimensions.estimate_points" },
  { key: ChartXAxisProperty.CREATED_BY, i18n_label: "reports.dimensions.created_by" },
  { key: ChartXAxisProperty.CREATED_AT, i18n_label: "reports.dimensions.created_at", is_date: true },
  { key: ChartXAxisProperty.COMPLETED_AT, i18n_label: "reports.dimensions.completed_at", is_date: true },
  { key: ChartXAxisProperty.START_DATE, i18n_label: "reports.dimensions.start_date", is_date: true },
  { key: ChartXAxisProperty.TARGET_DATE, i18n_label: "reports.dimensions.target_date", is_date: true },
];

export const REPORT_DATE_DIMENSIONS: TReportDimension[] = REPORT_DIMENSIONS.filter((d) => d.is_date).map((d) => d.key);

export const REPORT_METRICS: { key: TReportMetric; i18n_label: string }[] = [
  { key: ChartYAxisMetric.WORK_ITEM_COUNT, i18n_label: "reports.metrics.work_item_count" },
  { key: ChartYAxisMetric.ESTIMATE_POINT_COUNT, i18n_label: "reports.metrics.estimate_points" },
];

export const REPORT_DATE_GROUPINGS: { key: TReportDateGrouping; i18n_label: string }[] = [
  { key: "DAY", i18n_label: "reports.date_groupings.day" },
  { key: "WEEK", i18n_label: "reports.date_groupings.week" },
  { key: "MONTH", i18n_label: "reports.date_groupings.month" },
  { key: "YEAR", i18n_label: "reports.date_groupings.year" },
];

export const REPORT_DATE_FIELDS: { key: TReportDateField; i18n_label: string }[] = [
  { key: "created_at", i18n_label: "reports.date_fields.created_at" },
  { key: "completed_at", i18n_label: "reports.date_fields.completed_at" },
  { key: "start_date", i18n_label: "reports.date_fields.start_date" },
  { key: "target_date", i18n_label: "reports.date_fields.target_date" },
];

export const REPORT_DATE_PRESETS: { key: TReportDatePreset; i18n_label: string }[] = [
  { key: "last_7_days", i18n_label: "reports.date_presets.last_7_days" },
  { key: "last_30_days", i18n_label: "reports.date_presets.last_30_days" },
  { key: "last_90_days", i18n_label: "reports.date_presets.last_90_days" },
  { key: "this_month", i18n_label: "reports.date_presets.this_month" },
  { key: "last_month", i18n_label: "reports.date_presets.last_month" },
  { key: "this_quarter", i18n_label: "reports.date_presets.this_quarter" },
  { key: "this_year", i18n_label: "reports.date_presets.this_year" },
  { key: "custom", i18n_label: "reports.date_presets.custom" },
];

export const REPORT_TABLE_COLUMNS: { key: TReportTableColumn; i18n_label: string }[] = [
  { key: "sequence_id", i18n_label: "reports.columns.id" },
  { key: "name", i18n_label: "reports.columns.name" },
  { key: "project_identifier", i18n_label: "reports.columns.project" },
  { key: "state_name", i18n_label: "reports.columns.state" },
  { key: "state_group", i18n_label: "reports.columns.state_group" },
  { key: "priority", i18n_label: "reports.columns.priority" },
  { key: "assignees", i18n_label: "reports.columns.assignees" },
  { key: "labels", i18n_label: "reports.columns.labels" },
  { key: "start_date", i18n_label: "reports.columns.start_date" },
  { key: "target_date", i18n_label: "reports.columns.target_date" },
  { key: "completed_at", i18n_label: "reports.columns.completed_at" },
  { key: "created_at", i18n_label: "reports.columns.created_at" },
  { key: "estimate", i18n_label: "reports.columns.estimate" },
];

export const REPORT_CHART_TYPES: { key: TReportChartType; i18n_label: string }[] = [
  { key: "bar", i18n_label: "dashboards.widget.types.bar" },
  { key: "stacked_bar", i18n_label: "dashboards.widget.types.stacked_bar" },
  { key: "line", i18n_label: "dashboards.widget.types.line" },
  { key: "area", i18n_label: "dashboards.widget.types.area" },
  { key: "pie", i18n_label: "dashboards.widget.types.pie" },
  { key: "donut", i18n_label: "dashboards.widget.types.donut" },
  { key: "table", i18n_label: "dashboards.widget.types.table" },
];

export const DASHBOARD_WIDGET_TYPES: {
  key: TDashboardWidgetType;
  i18n_label: string;
  requires_dimension: boolean;
  allows_group_by: boolean;
  default_size: TDashboardWidgetSize;
}[] = [
  {
    key: "number",
    i18n_label: "dashboards.widget.types.number",
    requires_dimension: false,
    allows_group_by: false,
    default_size: "small",
  },
  {
    key: "bar",
    i18n_label: "dashboards.widget.types.bar",
    requires_dimension: true,
    allows_group_by: false,
    default_size: "medium",
  },
  {
    key: "stacked_bar",
    i18n_label: "dashboards.widget.types.stacked_bar",
    requires_dimension: true,
    allows_group_by: true,
    default_size: "medium",
  },
  {
    key: "line",
    i18n_label: "dashboards.widget.types.line",
    requires_dimension: true,
    allows_group_by: true,
    default_size: "large",
  },
  {
    key: "area",
    i18n_label: "dashboards.widget.types.area",
    requires_dimension: true,
    allows_group_by: true,
    default_size: "large",
  },
  {
    key: "pie",
    i18n_label: "dashboards.widget.types.pie",
    requires_dimension: true,
    allows_group_by: false,
    default_size: "medium",
  },
  {
    key: "donut",
    i18n_label: "dashboards.widget.types.donut",
    requires_dimension: true,
    allows_group_by: false,
    default_size: "medium",
  },
  {
    key: "table",
    i18n_label: "dashboards.widget.types.table",
    requires_dimension: false,
    allows_group_by: false,
    default_size: "full",
  },
];

export const DASHBOARD_WIDGET_SIZES: { key: TDashboardWidgetSize; i18n_label: string; className: string }[] = [
  { key: "small", i18n_label: "dashboards.widget.sizes.small", className: "col-span-1" },
  { key: "medium", i18n_label: "dashboards.widget.sizes.medium", className: "col-span-1 md:col-span-2" },
  { key: "large", i18n_label: "dashboards.widget.sizes.large", className: "col-span-1 md:col-span-2 xl:col-span-3" },
  { key: "full", i18n_label: "dashboards.widget.sizes.full", className: "col-span-full" },
];

export const DASHBOARD_ACCESS_OPTIONS: { key: 0 | 1; i18n_label: string; i18n_description: string }[] = [
  { key: 0, i18n_label: "dashboards.access.private", i18n_description: "dashboards.access.private_description" },
  { key: 1, i18n_label: "dashboards.access.workspace", i18n_description: "dashboards.access.workspace_description" },
];

export const DEFAULT_REPORT_QUERY_CONFIG: TReportQueryConfig = {
  metric: ChartYAxisMetric.WORK_ITEM_COUNT,
  x_axis: ChartXAxisProperty.STATE_GROUPS,
  group_by: null,
  date_grouping: null,
  project_ids: [],
  filters: {},
  date_range: null,
  include_sub_work_items: true,
};

export const DEFAULT_REPORT_TABLE_COLUMNS: TReportTableColumn[] = [
  "sequence_id",
  "name",
  "state_name",
  "priority",
  "assignees",
  "target_date",
];

/** Translation keys for raw values that appear in chart buckets (priorities, state groups, none/other). */
export const REPORT_VALUE_LABELS: Record<string, string> = {
  urgent: "reports.values.urgent",
  high: "reports.values.high",
  medium: "reports.values.medium",
  low: "reports.values.low",
  backlog: "reports.values.backlog",
  unstarted: "reports.values.unstarted",
  started: "reports.values.started",
  completed: "reports.values.completed",
  cancelled: "reports.values.cancelled",
  none: "reports.values.none",
  other: "reports.values.other",
};
