/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { useTheme } from "next-themes";
// plane imports
import { AreaChart } from "@plane/propel/charts/area-chart";
import { BarChart } from "@plane/propel/charts/bar-chart";
import { LineChart } from "@plane/propel/charts/line-chart";
import { PieChart } from "@plane/propel/charts/pie-chart";
import type {
  TAreaItem,
  TBarItem,
  TChart,
  TChartDatum,
  TLineItem,
  TReportChartType,
  TReportDisplay,
} from "@plane/types";
import { cn } from "@plane/utils";
// local imports
import { getPaletteColors } from "./utils";

type Props = {
  chartType: Exclude<TReportChartType, "table">;
  chart: TChart;
  display?: TReportDisplay;
  xLabel?: string;
  yLabel?: string;
  valueLabel: string;
  className?: string;
  compact?: boolean;
};

const LEGEND = { align: "center", verticalAlign: "bottom", layout: "horizontal" } as const;

export function ReportChartRenderer(props: Props) {
  const { chartType, chart, display, xLabel, yLabel, valueLabel, className, compact = false } = props;
  const { resolvedTheme } = useTheme();
  const segmentKeys = useMemo(() => Object.keys(chart.schema ?? {}), [chart.schema]);
  const showLegend = display?.show_legend !== false;
  const colors = useMemo(
    () => getPaletteColors(display, resolvedTheme, Math.max(segmentKeys.length, chart.data.length)),
    [display, resolvedTheme, segmentKeys.length, chart.data.length]
  );
  const datumColor = (datum: TChartDatum, index: number) =>
    typeof datum.color === "string" && datum.color ? datum.color : colors[index % colors.length];

  const margin = compact ? { top: 8, right: 8, bottom: 24, left: 0 } : { top: 8, right: 16, bottom: 36, left: 8 };
  const xAxis = { key: "name" as const, label: compact ? undefined : xLabel, dy: compact ? 8 : 24 };
  const yAxis = {
    key: "count" as const,
    label: compact ? undefined : yLabel,
    offset: -50,
    dx: -20,
    allowDecimals: false,
  };
  const rootClassName = cn("h-full w-full", className);

  if (chartType === "pie" || chartType === "donut") {
    const cells = chart.data.map((datum, index) => ({ key: String(datum.key), fill: datumColor(datum, index) }));
    return (
      <PieChart
        className={rootClassName}
        data={chart.data}
        dataKey="count"
        cells={cells}
        innerRadius={chartType === "donut" ? "55%" : 0}
        outerRadius="80%"
        paddingAngle={chartType === "donut" ? 2 : 0}
        cornerRadius={chartType === "donut" ? 4 : 0}
        showLabel={false}
        tooltipLabel={(payload: TChartDatum) => String(payload?.name ?? "")}
        legend={showLegend ? LEGEND : undefined}
      />
    );
  }

  if (chartType === "line") {
    const lines: TLineItem<string>[] = (segmentKeys.length ? segmentKeys : ["count"]).map((key, index) => ({
      key,
      label: segmentKeys.length ? chart.schema[key] : valueLabel,
      dashedLine: false,
      fill: colors[index % colors.length],
      stroke: colors[index % colors.length],
      showDot: true,
      smoothCurves: true,
    }));
    return (
      <LineChart
        className={rootClassName}
        data={chart.data}
        lines={lines}
        xAxis={xAxis}
        yAxis={yAxis}
        margin={margin}
        legend={showLegend && segmentKeys.length ? LEGEND : undefined}
      />
    );
  }

  if (chartType === "area") {
    const areas: TAreaItem<string>[] = (segmentKeys.length ? segmentKeys : ["count"]).map((key, index) => ({
      key,
      label: segmentKeys.length ? chart.schema[key] : valueLabel,
      stackId: "report-area",
      fill: colors[index % colors.length],
      fillOpacity: 0.35,
      strokeColor: colors[index % colors.length],
      strokeOpacity: 1,
      showDot: false,
      smoothCurves: true,
    }));
    return (
      <AreaChart
        className={rootClassName}
        data={chart.data}
        areas={areas}
        xAxis={xAxis}
        yAxis={yAxis}
        margin={margin}
        legend={showLegend && segmentKeys.length ? LEGEND : undefined}
      />
    );
  }

  // Bar and stacked bar
  let bars: TBarItem<string>[];
  if (segmentKeys.length) {
    const stacked = chartType === "stacked_bar";
    bars = segmentKeys.map((key, index) => ({
      key,
      label: chart.schema[key],
      stackId: stacked ? "report-stack" : `report-${key}`,
      fill: colors[index % colors.length],
      textClassName: "",
      showPercentage: false,
      showTopBorderRadius: (barKey: string, payload: TChartDatum) => {
        if (!stacked) return true;
        const present = segmentKeys.filter((k) => Number(payload[k]) > 0);
        return present[present.length - 1] === barKey;
      },
      showBottomBorderRadius: (barKey: string, payload: TChartDatum) => {
        if (!stacked) return true;
        return segmentKeys.find((k) => Number(payload[k]) > 0) === barKey;
      },
    }));
  } else {
    const colorByKey = new Map(chart.data.map((datum, index) => [String(datum.key), datumColor(datum, index)]));
    bars = [
      {
        key: "count",
        label: valueLabel,
        stackId: "report-single",
        fill: (payload: TChartDatum) => colorByKey.get(String(payload?.key)) ?? colors[0],
        textClassName: "",
        showPercentage: false,
        showTopBorderRadius: () => true,
        showBottomBorderRadius: () => true,
      },
    ];
  }

  return (
    <BarChart
      className={rootClassName}
      data={chart.data}
      bars={bars}
      xAxis={xAxis}
      yAxis={yAxis}
      margin={margin}
      barSize={compact ? 24 : 36}
      legend={showLegend && segmentKeys.length ? LEGEND : undefined}
    />
  );
}
