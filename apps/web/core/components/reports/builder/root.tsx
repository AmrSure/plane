/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Link2, Save, Settings2, Trash2 } from "lucide-react";
// plane imports
import {
  DEFAULT_REPORT_QUERY_CONFIG,
  DEFAULT_REPORT_TABLE_COLUMNS,
  REPORT_CHART_TYPES,
  REPORT_METRICS,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type {
  TReportChartType,
  TReportDisplay,
  TReportQueryConfig,
  TReportTableColumn,
  TSavedReport,
} from "@plane/types";
import { CustomMenu, CustomSelect } from "@plane/ui";
import { cn, copyUrlToClipboard } from "@plane/utils";
// components
import {
  ReportChartError,
  ReportChartLoader,
  ReportChartRenderer,
  ReportChartEmpty,
  ReportExportMenu,
  ReportNumberCard,
  ReportPivotTable,
  ReportQueryConfigForm,
  ReportWorkItemTable,
  buildExportLabels,
  decodeConfig,
  encodeConfig,
  getDimensionLabel,
  prepareChartData,
} from "@/components/report-charts";
// hooks
import useDebounce from "@/hooks/use-debounce";
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";
import { useAppRouter } from "@/hooks/use-app-router";
import { WorkspaceReportService } from "@/services/workspace-report.service";
// local imports
import { DeleteReportModal } from "../modals/delete-report-modal";
import { SaveReportModal } from "../modals/save-report-modal";

const reportService = new WorkspaceReportService();

const EXPORT_COLUMNS: TReportTableColumn[] = [
  "sequence_id",
  "name",
  "project_identifier",
  "state_name",
  "state_group",
  "priority",
  "assignees",
  "labels",
  "start_date",
  "target_date",
  "completed_at",
  "created_at",
  "estimate",
];

const DEFAULT_DISPLAY: TReportDisplay = { chart_type: "bar", palette: "modern", show_legend: true };

type Props = {
  workspaceSlug: string;
  reportId?: string;
};

export const ReportBuilder = observer(function ReportBuilder(props: Props) {
  const { workspaceSlug, reportId } = props;
  const { t } = useTranslation();
  const router = useAppRouter();
  const searchParams = useSearchParams();
  const { fetchReport, getReportById, updateReport } = useWorkspaceReport();

  const [config, setConfig] = useState<TReportQueryConfig>(
    () => decodeConfig(searchParams.get("q")) ?? { ...DEFAULT_REPORT_QUERY_CONFIG }
  );
  const [display, setDisplay] = useState<TReportDisplay>(DEFAULT_DISPLAY);
  const [modal, setModal] = useState<"save" | "save_as" | "settings" | "delete" | null>(null);
  const [initializedFor, setInitializedFor] = useState<string | undefined>(undefined);

  const { error: reportError } = useSWR(
    reportId ? `SAVED_REPORT_${workspaceSlug}_${reportId}` : null,
    () => fetchReport(workspaceSlug, reportId as string),
    { revalidateOnFocus: false }
  );
  const report = reportId ? getReportById(reportId) : undefined;

  useEffect(() => {
    if (report && initializedFor !== report.id) {
      setConfig(report.config);
      setDisplay({ ...DEFAULT_DISPLAY, ...report.display });
      setInitializedFor(report.id);
    }
  }, [report, initializedFor]);

  const queryKey = useDebounce(JSON.stringify(config), 400);
  const {
    data: result,
    error,
    isLoading,
    mutate,
  } = useSWR(
    reportId && !initializedFor ? null : `REPORT_QUERY_${workspaceSlug}_${queryKey}`,
    () => reportService.query(workspaceSlug, JSON.parse(queryKey) as TReportQueryConfig),
    { revalidateOnFocus: false, keepPreviousData: true }
  );

  const chartType = (display.chart_type ?? "bar") as TReportChartType;
  const chart = useMemo(
    () => (result?.chart ? prepareChartData(result.chart, config, t) : undefined),
    [result, config, t]
  );
  const metricLabel = t(
    REPORT_METRICS.find((m) => m.key === config.metric)?.i18n_label ?? "reports.metrics.work_item_count"
  );
  const dimensionLabel = getDimensionLabel(t, config.x_axis);
  const isDirty =
    !report ||
    JSON.stringify(report.config) !== JSON.stringify(config) ||
    report.display.chart_type !== display.chart_type;
  const title = report?.name ?? t("reports.builder.new_title");

  const setChartType = (type: TReportChartType) => {
    setDisplay((prev) => ({ ...prev, chart_type: type }));
    if ((type === "pie" || type === "donut") && config.group_by) setConfig((prev) => ({ ...prev, group_by: null }));
  };

  const handleCopyLink = () => {
    const path =
      report && !isDirty
        ? `${workspaceSlug}/reports/${report.id}`
        : `${workspaceSlug}/reports/new?q=${encodeConfig(config)}`;
    copyUrlToClipboard(path).then(() => setToast({ type: TOAST_TYPE.SUCCESS, title: t("reports.toast.link_copied") }));
  };

  const handleSave = async () => {
    if (!report?.is_owner) return setModal("save_as");
    try {
      await updateReport(workspaceSlug, report.id, { config, display });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("reports.toast.saved") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("reports.toast.error") });
    }
  };

  const handleExport = (format: "csv" | "xlsx") =>
    reportService.exportReport(workspaceSlug, {
      config: { ...config, table: { columns: EXPORT_COLUMNS } },
      format,
      title,
      labels: buildExportLabels(t, config),
    });

  if (reportId && reportError && !report) {
    return (
      <EmptyStateDetailed
        assetKey="invalid-link"
        title={t("reports.not_found.title")}
        description={t("reports.not_found.description")}
      />
    );
  }

  const table = result?.table;
  const meta = result?.chart?.meta ?? result?.number?.meta;
  const workItemCount = result?.chart?.totals.work_item_count ?? result?.number?.work_item_count ?? 0;

  return (
    <div className="flex h-full w-full flex-col overflow-hidden md:flex-row">
      <SaveReportModal
        workspaceSlug={workspaceSlug}
        isOpen={modal === "save" || modal === "save_as" || modal === "settings"}
        onClose={() => setModal(null)}
        config={config}
        display={display}
        report={modal === "settings" ? report : undefined}
        onSaved={(saved: TSavedReport) => {
          if (modal !== "settings") router.push(`/${workspaceSlug}/reports/${saved.id}`);
        }}
      />
      {report && (
        <DeleteReportModal
          workspaceSlug={workspaceSlug}
          report={report}
          isOpen={modal === "delete"}
          onClose={() => setModal(null)}
          redirectOnDelete
        />
      )}

      {/* Configuration panel */}
      <aside className="flex w-full flex-shrink-0 flex-col gap-5 overflow-y-auto border-b border-subtle p-5 md:w-80 md:border-r md:border-b-0">
        <div className="flex flex-col gap-1.5">
          <span className="text-11 font-medium text-tertiary uppercase">{t("reports.builder.chart_type")}</span>
          <CustomSelect
            value={chartType}
            label={t(REPORT_CHART_TYPES.find((c) => c.key === chartType)?.i18n_label ?? "dashboards.widget.types.bar")}
            onChange={setChartType}
            buttonClassName="w-full justify-between"
          >
            {REPORT_CHART_TYPES.map((type) => (
              <CustomSelect.Option key={type.key} value={type.key}>
                {t(type.i18n_label)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>
        <ReportQueryConfigForm
          workspaceSlug={workspaceSlug}
          value={config}
          onChange={setConfig}
          requireDimension={false}
          allowGroupBy={chartType !== "pie" && chartType !== "donut"}
        />
      </aside>

      {/* Results */}
      <section className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-subtle px-6 py-3">
          <div className="flex min-w-0 flex-col">
            <span className="flex items-center gap-2 truncate text-16 font-medium text-primary">
              {title}
              {report && isDirty && (
                <span className="font-normal rounded-sm bg-layer-2 px-1.5 py-0.5 text-11 text-tertiary">
                  {t("reports.builder.unsaved")}
                </span>
              )}
            </span>
            {meta && (
              <span className="text-12 text-tertiary">
                {t("reports.builder.result_summary", { count: workItemCount, projects: meta.project_count })}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="lg" prependIcon={<Link2 className="size-3.5" />} onClick={handleCopyLink}>
              {t("reports.builder.copy_link")}
            </Button>
            <ReportExportMenu onExport={handleExport} />
            {(!report || report.is_owner) && (
              <Button
                variant="primary"
                size="lg"
                prependIcon={<Save className="size-3.5" />}
                onClick={report ? handleSave : () => setModal("save")}
                disabled={Boolean(report) && !isDirty}
              >
                {t("reports.builder.save")}
              </Button>
            )}
            {report && (
              <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
                <CustomMenu.MenuItem onClick={() => setModal("save_as")}>
                  <span className="flex items-center gap-2">
                    <Save className="size-3.5" />
                    {t("reports.builder.save_as")}
                  </span>
                </CustomMenu.MenuItem>
                {report.is_owner && (
                  <CustomMenu.MenuItem onClick={() => setModal("settings")}>
                    <span className="flex items-center gap-2">
                      <Settings2 className="size-3.5" />
                      {t("reports.save_modal.edit_title")}
                    </span>
                  </CustomMenu.MenuItem>
                )}
                {report.is_owner && (
                  <CustomMenu.MenuItem onClick={() => setModal("delete")}>
                    <span className="flex items-center gap-2 text-danger-primary">
                      <Trash2 className="size-3.5" />
                      {t("reports.delete.title")}
                    </span>
                  </CustomMenu.MenuItem>
                )}
              </CustomMenu>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-6 p-6">
          {isLoading && !result ? (
            <div className="h-[22rem] rounded-lg border border-subtle p-4">
              <ReportChartLoader />
            </div>
          ) : error ? (
            <div className="h-[22rem] rounded-lg border border-subtle">
              <ReportChartError error={error} onRetry={() => mutate()} timeoutKey="reports.errors.timeout" />
            </div>
          ) : (
            <>
              {result?.number && (
                <div className="rounded-lg border border-subtle p-5">
                  <ReportNumberCard result={result.number} />
                </div>
              )}
              {chart && chartType !== "table" && (
                <div className={cn("rounded-lg border border-subtle p-4", "h-[24rem]")}>
                  {chart.data.length === 0 ? (
                    <ReportChartEmpty />
                  ) : (
                    <ReportChartRenderer
                      chartType={chartType}
                      chart={chart}
                      display={display}
                      xLabel={dimensionLabel}
                      yLabel={metricLabel}
                      valueLabel={metricLabel}
                    />
                  )}
                </div>
              )}
              {chart && chart.data.length > 0 && (
                <div className="rounded-lg border border-subtle">
                  <ReportPivotTable chart={chart} dimensionLabel={dimensionLabel} />
                </div>
              )}
              {table && (
                <div className="flex flex-col gap-2">
                  <span className="text-14 font-medium text-primary">{t("reports.builder.table_title")}</span>
                  {table.results.length === 0 ? (
                    <div className="rounded-lg border border-subtle">
                      <ReportChartEmpty />
                    </div>
                  ) : (
                    <div className="rounded-lg border border-subtle">
                      <ReportWorkItemTable
                        workspaceSlug={workspaceSlug}
                        rows={table.results}
                        columns={table.meta.columns ?? DEFAULT_REPORT_TABLE_COLUMNS}
                      />
                    </div>
                  )}
                  {table.total_count > table.results.length && (
                    <span className="text-12 text-tertiary">
                      {t("reports.builder.table_truncated", { shown: table.results.length, total: table.total_count })}
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
});
