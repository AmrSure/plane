/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { REPORT_METRICS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TDashboardWidgetType, TReportDisplay, TReportQueryConfig, TReportWidgetResult } from "@plane/types";
import { cn } from "@plane/utils";
// local imports
import { ReportChartRenderer } from "./chart-renderer";
import { ReportNumberCard } from "./number-card";
import { ReportChartEmpty } from "./states";
import { getDimensionLabel, prepareChartData } from "./utils";
import { ReportWorkItemTable } from "./work-item-table";

type Props = {
  workspaceSlug: string;
  widgetType: TDashboardWidgetType;
  result: TReportWidgetResult;
  config: TReportQueryConfig;
  display?: TReportDisplay;
  compact?: boolean;
  className?: string;
};

export function ReportResultView(props: Props) {
  const { workspaceSlug, widgetType, result, config, display, compact = true, className } = props;
  const { t } = useTranslation();
  const chart = useMemo(
    () => (result.kind === "chart" ? prepareChartData(result, config, t) : undefined),
    [result, config, t]
  );
  const metricLabel = t(
    REPORT_METRICS.find((m) => m.key === config.metric)?.i18n_label ?? "reports.metrics.work_item_count"
  );

  if (result.kind === "number") return <ReportNumberCard result={result} className={className} />;

  if (result.kind === "table") {
    if (result.results.length === 0) return <ReportChartEmpty className={className} />;
    return (
      <ReportWorkItemTable
        workspaceSlug={workspaceSlug}
        rows={result.results}
        columns={result.meta.columns ?? config.table?.columns ?? ["sequence_id", "name"]}
        className={cn("h-full overflow-y-auto", className)}
      />
    );
  }

  if (!chart || chart.data.length === 0) return <ReportChartEmpty className={className} />;
  return (
    <ReportChartRenderer
      chartType={widgetType === "number" || widgetType === "table" ? "bar" : widgetType}
      chart={chart}
      display={display}
      xLabel={getDimensionLabel(t, config.x_axis)}
      yLabel={metricLabel}
      valueLabel={metricLabel}
      compact={compact}
      className={className}
    />
  );
}
