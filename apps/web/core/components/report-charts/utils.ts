/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ChartXAxisDateGrouping } from "@plane/constants";
import { CHART_COLOR_PALETTES, REPORT_DIMENSIONS, REPORT_TABLE_COLUMNS, REPORT_VALUE_LABELS } from "@plane/constants";
import type {
  ChartXAxisProperty,
  TChart,
  TChartDatum,
  TReportChartResult,
  TReportDisplay,
  TReportExportLabels,
  TReportFilterExpression,
  TReportQueryConfig,
} from "@plane/types";
import { generateExtendedColors, parseChartData } from "@/components/chart/utils";

type TTranslate = (key: string, params?: Record<string, unknown>) => string;

const TRANSLATED_DIMENSIONS = new Set<string>(["PRIORITY", "STATE_GROUPS"]);

const translateValue = (t: TTranslate, dimension: string | null | undefined, key: string, name: string) => {
  if (key === "none" || key === "other") return t(REPORT_VALUE_LABELS[key]);
  if (dimension && TRANSLATED_DIMENSIONS.has(dimension) && REPORT_VALUE_LABELS[key]) return t(REPORT_VALUE_LABELS[key]);
  return name;
};

/** Parse a chart result for display: fill missing segments, format dates and translate known values. */
export const prepareChartData = (
  result: TReportChartResult | undefined,
  config: TReportQueryConfig,
  t: TTranslate
): TChart => {
  if (!result) return { data: [], schema: {} };
  const parsed = parseChartData(
    { data: result.data as unknown as TChartDatum[], schema: result.schema },
    (config.x_axis ?? null) as ChartXAxisProperty | null,
    (config.group_by ?? null) as ChartXAxisProperty | null,
    (config.date_grouping ?? null) as ChartXAxisDateGrouping | null
  );
  // TChartDatum types every extra field as a number; names and colors are strings at runtime.
  const data = parsed.data.map((datum) => ({
    ...datum,
    name: translateValue(t, config.x_axis, String(datum.key), String(datum.name)),
  })) as unknown as TChartDatum[];
  const schema = Object.fromEntries(
    Object.entries(parsed.schema).map(([key, name]) => [key, translateValue(t, config.group_by, key, String(name))])
  );
  return { data, schema };
};

export const getPaletteColors = (display: TReportDisplay | undefined, theme: string | undefined, count: number) => {
  const palette = CHART_COLOR_PALETTES.find((p) => p.key === (display?.palette ?? "modern")) ?? CHART_COLOR_PALETTES[0];
  const base = palette[theme === "dark" ? "dark" : "light"];
  return generateExtendedColors(base, Math.max(count, 1));
};

export const getDimensionLabel = (t: TTranslate, dimension: string | null | undefined) => {
  const option = REPORT_DIMENSIONS.find((d) => d.key === dimension);
  return option ? t(option.i18n_label) : "";
};

// ------------------------------------------------------------------ structured filters

export type TStructuredFilters = {
  state_groups: string[];
  priorities: string[];
  assignee_ids: string[];
  label_ids: string[];
};

export const EMPTY_STRUCTURED_FILTERS: TStructuredFilters = {
  state_groups: [],
  priorities: [],
  assignee_ids: [],
  label_ids: [],
};

const FILTER_FIELDS: Record<keyof TStructuredFilters, string> = {
  state_groups: "state_group__in",
  priorities: "priority__in",
  assignee_ids: "assignee_id__in",
  label_ids: "label_id__in",
};

/** Compile structured filters into the rich filter expression the API accepts. */
export const toFilterExpression = (filters: TStructuredFilters): TReportFilterExpression => {
  const conditions = (Object.keys(FILTER_FIELDS) as (keyof TStructuredFilters)[])
    .filter((key) => filters[key].length > 0)
    .map((key) => ({ [FILTER_FIELDS[key]]: filters[key].join(",") }));
  if (conditions.length === 0) return {};
  if (conditions.length === 1) return conditions[0];
  return { and: conditions };
};

const splitValue = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string" && value.length > 0) return value.split(",");
  return [];
};

/** Read structured filters back from an expression produced by toFilterExpression. */
export const fromFilterExpression = (expression: TReportFilterExpression | undefined): TStructuredFilters => {
  const result: TStructuredFilters = { ...EMPTY_STRUCTURED_FILTERS };
  if (!expression) return result;
  const leaves: Record<string, unknown>[] = Array.isArray(expression.and)
    ? (expression.and as Record<string, unknown>[])
    : [expression as Record<string, unknown>];
  leaves.forEach((leaf) => {
    (Object.keys(FILTER_FIELDS) as (keyof TStructuredFilters)[]).forEach((key) => {
      if (FILTER_FIELDS[key] in leaf) result[key] = splitValue(leaf[FILTER_FIELDS[key]]);
    });
  });
  return result;
};

export const countActiveFilters = (config: TReportQueryConfig) => {
  const filters = fromFilterExpression(config.filters);
  return (
    Object.values(filters).filter((values) => values.length > 0).length +
    ((config.project_ids?.length ?? 0) > 0 ? 1 : 0) +
    (config.date_range ? 1 : 0)
  );
};

// ------------------------------------------------------------------ export labels

export const buildExportLabels = (t: TTranslate, config: TReportQueryConfig): TReportExportLabels => ({
  dimension: getDimensionLabel(t, config.x_axis) || t("reports.builder.dimension"),
  total: t("reports.builder.total"),
  values: Object.fromEntries(Object.entries(REPORT_VALUE_LABELS).map(([key, label]) => [key, t(label)])),
  columns: Object.fromEntries(REPORT_TABLE_COLUMNS.map((column) => [column.key, t(column.i18n_label)])),
  sheets: { summary: t("reports.export.sheets.summary"), items: t("reports.export.sheets.items") },
});

// ------------------------------------------------------------------ permalinks

export const encodeConfig = (config: TReportQueryConfig): string => {
  const json = JSON.stringify(config);
  const bytes = new TextEncoder().encode(json);
  let binary = "";
  bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

export const decodeConfig = (value: string | null | undefined): TReportQueryConfig | undefined => {
  if (!value) return undefined;
  try {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64 + "===".slice((base64.length + 3) % 4));
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    const parsed = JSON.parse(new TextDecoder().decode(bytes));
    return parsed && typeof parsed === "object" ? (parsed as TReportQueryConfig) : undefined;
  } catch {
    return undefined;
  }
};

/** API error payloads: DRF field errors or {error, code}. */
export const getErrorCode = (error: unknown): string | undefined =>
  error && typeof error === "object" && "code" in error ? String((error as { code: unknown }).code) : undefined;
