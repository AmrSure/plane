/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import useSWR from "swr";
import { Download, Info } from "lucide-react";
// plane imports
import { CHART_COLOR_PALETTES, REPORT_VALUE_LABELS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { getButtonStyling } from "@plane/propel/button";
import { LineChart } from "@plane/propel/charts/line-chart";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { Tabs } from "@plane/propel/tabs";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import type {
  TChart,
  TCycleReportBreakdownRow,
  TCycleReportItem,
  TCycleReportSection,
  TReportExportFormat,
  TReportTableRow,
} from "@plane/types";
import { CustomMenu, Loader } from "@plane/ui";
import { cn, renderFormattedDate } from "@plane/utils";
// components
import { ReportChartRenderer, ReportWorkItemTable } from "@/components/report-charts";
// services
import { WorkspaceReportService } from "@/services/workspace-report.service";

const reportService = new WorkspaceReportService();

type TBreakdownKey = "assignees" | "labels" | "state_groups" | "priorities";

const BREAKDOWN_TABS: { key: TBreakdownKey; i18n: string }[] = [
  { key: "assignees", i18n: "cycle_report.breakdown.assignees" },
  { key: "labels", i18n: "cycle_report.breakdown.labels" },
  { key: "state_groups", i18n: "cycle_report.breakdown.state_groups" },
  { key: "priorities", i18n: "cycle_report.breakdown.priorities" },
];

const SECTIONS: { key: TCycleReportSection; i18n: string }[] = [
  { key: "summary", i18n: "cycle_report.summary.scope" },
  { key: "burndown", i18n: "cycle_report.burndown.title" },
  { key: "assignees", i18n: "cycle_report.breakdown.assignees" },
  { key: "labels", i18n: "cycle_report.breakdown.labels" },
  { key: "state_groups", i18n: "cycle_report.breakdown.state_groups" },
  { key: "priorities", i18n: "cycle_report.breakdown.priorities" },
  { key: "scope_changes", i18n: "cycle_report.scope_changes.title" },
  { key: "incomplete_items", i18n: "cycle_report.incomplete.title" },
];

const ITEM_COLUMNS = ["sequence_id", "name", "state_name", "priority", "assignees", "target_date", "estimate"] as const;

function StatCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-subtle bg-surface-1 px-4 py-3">
      <span className="text-12 text-tertiary">{label}</span>
      <span className="text-24 font-semibold text-primary tabular-nums">{value}</span>
      {hint && <span className="text-11 text-tertiary">{hint}</span>}
    </div>
  );
}

type Props = {
  workspaceSlug: string;
  projectId: string;
  cycleId: string;
};

export const CycleReport = observer(function CycleReport(props: Props) {
  const { workspaceSlug, projectId, cycleId } = props;
  const { t, currentLocale } = useTranslation();
  const { resolvedTheme } = useTheme();
  const searchParams = useSearchParams();
  const [usePoints, setUsePoints] = useState(searchParams.get("metric") === "points");
  const [breakdownTab, setBreakdownTab] = useState<TBreakdownKey>("assignees");

  const {
    data: report,
    error,
    isLoading,
  } = useSWR(
    `CYCLE_REPORT_${workspaceSlug}_${projectId}_${cycleId}`,
    () => reportService.getCycleReport(workspaceSlug, projectId, cycleId),
    { revalidateOnFocus: false }
  );

  const colors = CHART_COLOR_PALETTES[0][resolvedTheme === "dark" ? "dark" : "light"];
  const number = (value: number) => new Intl.NumberFormat(currentLocale, { maximumFractionDigits: 1 }).format(value);
  const valueLabel = (row: TCycleReportBreakdownRow, kind: TBreakdownKey) => {
    if (row.id === "none")
      return kind === "labels" ? t("cycle_report.breakdown.no_label") : t("cycle_report.breakdown.unassigned");
    if ((kind === "state_groups" || kind === "priorities") && REPORT_VALUE_LABELS[row.id])
      return t(REPORT_VALUE_LABELS[row.id]);
    return row.name;
  };

  const burndownData = useMemo(() => {
    if (!report) return [];
    const series = usePoints && report.burndown.points ? report.burndown.points : report.burndown.issues;
    const total = usePoints && report.summary.points ? report.summary.points.total : report.summary.total;
    const dates = report.burndown.dates;
    return dates.map((date, index) => ({
      key: date,
      name: renderFormattedDate(date) ?? date,
      ideal: dates.length > 1 ? Math.round(total * (1 - index / (dates.length - 1)) * 10) / 10 : total,
      remaining: series?.[date] ?? null,
    }));
  }, [report, usePoints]);

  const breakdownChart: TChart | undefined = useMemo(() => {
    if (!report) return undefined;
    const rows = report.breakdown[breakdownTab];
    return {
      data: rows.map((row) => ({
        key: row.id,
        name: valueLabel(row, breakdownTab),
        count: usePoints && row.points_total != null ? row.points_total : row.total,
        color: row.color ?? undefined,
      })) as unknown as TChart["data"],
      schema: {},
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report, breakdownTab, usePoints, t]);

  const handleExport = async (format: TReportExportFormat, section?: TCycleReportSection) => {
    try {
      await reportService.exportCycleReport(workspaceSlug, projectId, cycleId, {
        format,
        section,
        labels: {
          columns: {
            metric: t("cycle_report.columns.metric"),
            value: t("cycle_report.columns.value"),
            date: t("cycle_report.columns.date"),
            remaining_issues: t("cycle_report.columns.remaining_issues"),
            remaining_points: t("cycle_report.columns.remaining_points"),
            name: t("cycle_report.breakdown.name"),
            total: t("cycle_report.breakdown.total"),
            completed: t("cycle_report.breakdown.completed"),
            pending: t("cycle_report.breakdown.pending"),
            cancelled: t("cycle_report.summary.cancelled"),
            completion_pct: t("cycle_report.summary.completion"),
            days_total: t("cycle_report.columns.days_total"),
            days_left: t("cycle_report.summary.days_left"),
            points_total: t("cycle_report.columns.points_total"),
            points_completed: t("cycle_report.columns.points_completed"),
            change: t("cycle_report.columns.change"),
            added: t("cycle_report.scope_changes.added"),
            removed: t("cycle_report.scope_changes.removed"),
            id: t("cycle_report.columns.id"),
            state: t("cycle_report.columns.state"),
            priority: t("cycle_report.columns.priority"),
            assignees: t("cycle_report.columns.assignees"),
            target_date: t("cycle_report.columns.target_date"),
            estimate: t("cycle_report.columns.estimate"),
          },
          values: {
            ...Object.fromEntries(Object.entries(REPORT_VALUE_LABELS).map(([key, label]) => [key, t(label)])),
            none: t("cycle_report.breakdown.unassigned"),
          },
          sheets: Object.fromEntries(SECTIONS.map((s) => [s.key, t(s.i18n)])),
        },
      });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("reports.export.error") });
    }
  };

  if (isLoading && !report) {
    return (
      <Loader className="grid grid-cols-2 gap-4 p-6 lg:grid-cols-5">
        {[1, 2, 3, 4, 5].map((item) => (
          <Loader.Item key={item} height="84px" />
        ))}
        <Loader.Item height="20rem" className="col-span-full" />
      </Loader>
    );
  }

  if (error || !report) {
    const code = (error as { code?: string } | undefined)?.code;
    const message =
      code === "no_dates"
        ? t("cycle_report.errors.no_dates")
        : code === "guest_restricted"
          ? t("cycle_report.errors.guest_restricted")
          : t("cycle_report.errors.generic");
    return (
      <EmptyStateDetailed
        assetKey={code === "guest_restricted" ? "no-access" : "cycle"}
        title={t("cycle_report.title")}
        description={message}
      />
    );
  }

  const { summary, cycle, scope_changes: scope } = report;
  const pointsAvailable = Boolean(summary.points);
  const showPoints = usePoints && pointsAvailable;
  const toRow = (item: TCycleReportItem): TReportTableRow => ({
    id: item.id,
    project_id: cycle.project_id,
    sequence_id: item.sequence_id,
    project_identifier: item.project_identifier,
    name: item.name,
    state_name: item.state_name ?? undefined,
    state_group: item.state_group ?? undefined,
    state_color: item.state_color,
    priority: item.priority,
    assignees: item.assignees,
    target_date: item.target_date,
    estimate: item.estimate,
  });

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-y-auto p-6">
      {/* Title row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h2 className="text-18 font-semibold text-primary">{cycle.name}</h2>
            <span className="rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 text-secondary">
              {t(`cycle_report.status.${cycle.status}`)}
            </span>
            <Tooltip
              tooltipContent={
                cycle.source === "snapshot"
                  ? t("cycle_report.source.snapshot_hint")
                  : t("cycle_report.source.live_hint")
              }
            >
              <span className="flex items-center gap-1 rounded-sm border border-subtle px-1.5 py-0.5 text-11 text-tertiary">
                <Info className="size-3" />
                {cycle.source === "snapshot" ? t("cycle_report.source.snapshot") : t("cycle_report.source.live")}
              </span>
            </Tooltip>
          </div>
          <span className="text-12 text-tertiary">
            {renderFormattedDate(cycle.start_date)} – {renderFormattedDate(cycle.end_date)} ·{" "}
            {t("cycle_report.summary.elapsed", { elapsed: summary.days_elapsed, total: summary.days_total })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {pointsAvailable && (
            <div className="flex rounded-md border border-subtle p-0.5">
              {[false, true].map((points) => (
                <button
                  key={String(points)}
                  type="button"
                  onClick={() => setUsePoints(points)}
                  className={cn("rounded-sm px-2.5 py-1 text-12", {
                    "bg-layer-2 font-medium text-primary": usePoints === points,
                    "text-tertiary": usePoints !== points,
                  })}
                >
                  {points ? t("cycle_report.toggle.points") : t("cycle_report.toggle.issues")}
                </button>
              ))}
            </div>
          )}
          <CustomMenu
            placement="bottom-end"
            closeOnSelect
            customButton={
              <span className={cn(getButtonStyling("secondary", "lg"), "gap-1.5")}>
                <Download className="size-3.5" />
                {t("reports.export.label")}
              </span>
            }
          >
            <CustomMenu.MenuItem onClick={() => handleExport("xlsx")}>
              {t("cycle_report.export.workbook")}
            </CustomMenu.MenuItem>
            {SECTIONS.map((section) => (
              <CustomMenu.MenuItem key={section.key} onClick={() => handleExport("csv", section.key)}>
                {t(section.i18n)} (CSV)
              </CustomMenu.MenuItem>
            ))}
          </CustomMenu>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard
          label={t("cycle_report.summary.scope")}
          value={number(showPoints && summary.points ? summary.points.total : summary.total)}
        />
        <StatCard
          label={t("cycle_report.summary.completed")}
          value={number(showPoints && summary.points ? summary.points.completed : summary.completed)}
          hint={`${number(showPoints && summary.points ? summary.points.completion_pct : summary.completion_pct)}%`}
        />
        <StatCard
          label={t("cycle_report.summary.pending")}
          value={number(showPoints && summary.points ? summary.points.pending : summary.pending)}
        />
        <StatCard
          label={t("cycle_report.summary.cancelled")}
          value={number(showPoints && summary.points ? summary.points.cancelled : summary.cancelled)}
        />
        <StatCard
          label={t("cycle_report.summary.days_left")}
          value={summary.days_left}
          hint={t("cycle_report.summary.days_left_count", { count: summary.days_left })}
        />
      </div>

      {/* Burndown */}
      <div className="flex flex-col gap-2 rounded-lg border border-subtle p-4">
        <span className="text-14 font-medium text-primary">{t("cycle_report.burndown.title")}</span>
        <div className="h-[20rem]">
          <LineChart
            className="h-full w-full"
            data={burndownData as unknown as TChart["data"]}
            lines={[
              {
                key: "ideal",
                label: t("cycle_report.burndown.ideal"),
                dashedLine: true,
                fill: "#94a3b8",
                stroke: "#94a3b8",
                showDot: false,
                smoothCurves: false,
              },
              {
                key: "remaining",
                label: t("cycle_report.burndown.remaining"),
                dashedLine: false,
                fill: colors[0],
                stroke: colors[0],
                showDot: true,
                smoothCurves: false,
              },
            ]}
            xAxis={{ key: "name", dy: 16 }}
            yAxis={{ key: "remaining", allowDecimals: false, offset: -50, dx: -20 }}
            margin={{ top: 8, right: 16, bottom: 24, left: 0 }}
            legend={{ align: "center", verticalAlign: "bottom", layout: "horizontal" }}
          />
        </div>
      </div>

      {/* Breakdown */}
      <div className="flex flex-col gap-3 rounded-lg border border-subtle p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-14 font-medium text-primary">{t("cycle_report.breakdown.title")}</span>
          <Tabs value={breakdownTab} onValueChange={(value) => setBreakdownTab(value as TBreakdownKey)}>
            <Tabs.List className="flex h-7 w-fit">
              {BREAKDOWN_TABS.map((tab) => (
                <Tabs.Trigger key={tab.key} value={tab.key} size="md" className="h-6 px-3">
                  {t(tab.i18n)}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
          </Tabs>
        </div>
        {breakdownTab === "priorities" && (
          <span className="text-11 text-tertiary">{t("cycle_report.source.priorities_live")}</span>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="h-[18rem]">
            {breakdownChart && breakdownChart.data.length > 0 && (
              <ReportChartRenderer
                chartType="bar"
                chart={breakdownChart}
                valueLabel={showPoints ? t("cycle_report.toggle.points") : t("cycle_report.toggle.issues")}
                compact
              />
            )}
          </div>
          <div className="max-h-[18rem] overflow-y-auto">
            <table className="w-full text-13">
              <thead className="sticky top-0 bg-surface-1 text-left text-12 text-tertiary">
                <tr>
                  <th className="py-1.5 font-medium">{t("cycle_report.breakdown.name")}</th>
                  <th className="py-1.5 text-right font-medium">{t("cycle_report.breakdown.total")}</th>
                  {breakdownTab !== "state_groups" && breakdownTab !== "priorities" && (
                    <>
                      <th className="py-1.5 text-right font-medium">{t("cycle_report.breakdown.completed")}</th>
                      <th className="py-1.5 text-right font-medium">{t("cycle_report.breakdown.pending")}</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {report.breakdown[breakdownTab].map((row) => (
                  <tr key={row.id} className="border-t border-subtle">
                    <td className="py-1.5 pr-2">
                      <span className="flex items-center gap-2">
                        {row.color && <span className="size-2 rounded-full" style={{ backgroundColor: row.color }} />}
                        {valueLabel(row, breakdownTab)}
                      </span>
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{row.total}</td>
                    {breakdownTab !== "state_groups" && breakdownTab !== "priorities" && (
                      <>
                        <td className="py-1.5 text-right tabular-nums">{row.completed ?? "-"}</td>
                        <td className="py-1.5 text-right tabular-nums">{row.pending ?? "-"}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Scope changes */}
      <div className="flex flex-col gap-3 rounded-lg border border-subtle p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-14 font-medium text-primary">{t("cycle_report.scope_changes.title")}</span>
          {scope.available && (
            <span className="text-12 text-tertiary">
              {t("cycle_report.scope_changes.added")}: {scope.added.length} · {t("cycle_report.scope_changes.removed")}:{" "}
              {scope.removed.length} · {t("cycle_report.scope_changes.net")}: {scope.net_change > 0 ? "+" : ""}
              {scope.net_change}
            </span>
          )}
        </div>
        {!scope.available ? (
          <p className="text-13 text-tertiary">{t("cycle_report.scope_changes.unavailable")}</p>
        ) : scope.added.length + scope.removed.length === 0 ? (
          <p className="text-13 text-tertiary">{t("cycle_report.scope_changes.none")}</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {(["added", "removed"] as const).map((kind) => (
              <div key={kind} className="flex flex-col gap-1">
                <span className="text-12 font-medium text-secondary">{t(`cycle_report.scope_changes.${kind}`)}</span>
                {scope[kind].map((item) => (
                  <span key={item.id} className="flex items-center gap-2 text-13 text-secondary">
                    <span className="flex-shrink-0 text-tertiary">
                      {item.project_identifier}-{item.sequence_id}
                    </span>
                    <span className="truncate">{item.name}</span>
                    <span className="ml-auto flex-shrink-0 text-11 text-tertiary">{renderFormattedDate(item.at)}</span>
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
        <span className="text-11 text-tertiary">{t("cycle_report.scope_changes.accuracy_note")}</span>
      </div>

      {/* Incomplete / transferred items */}
      <div className="flex flex-col gap-2 rounded-lg border border-subtle p-4">
        <span className="text-14 font-medium text-primary">
          {cycle.source === "snapshot"
            ? t("cycle_report.incomplete.transferred_title")
            : t("cycle_report.incomplete.title")}
        </span>
        {(() => {
          const items = cycle.source === "snapshot" ? report.transferred_items : report.incomplete_items.results;
          if (items.length === 0) return <p className="text-13 text-tertiary">{t("cycle_report.incomplete.empty")}</p>;
          return (
            <>
              <ReportWorkItemTable workspaceSlug={workspaceSlug} rows={items.map(toRow)} columns={[...ITEM_COLUMNS]} />
              {report.incomplete_items.truncated && cycle.source !== "snapshot" && (
                <span className="text-12 text-tertiary">
                  {t("cycle_report.incomplete.truncated", { count: report.incomplete_items.results.length })}
                </span>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
});
