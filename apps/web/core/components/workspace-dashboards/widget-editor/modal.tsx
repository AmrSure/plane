/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { BarChart3, ChartArea, ChartLine, ChartPie, Hash, Layers, PieChart, Table2 } from "lucide-react";
// plane imports
import {
  CHART_COLOR_PALETTES,
  DASHBOARD_WIDGET_SIZES,
  DASHBOARD_WIDGET_TYPES,
  DEFAULT_REPORT_QUERY_CONFIG,
  DEFAULT_REPORT_TABLE_COLUMNS,
  REPORT_TABLE_COLUMNS,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type {
  TDashboardWidget,
  TDashboardWidgetFormData,
  TDashboardWidgetSize,
  TDashboardWidgetType,
  TReportQueryConfig,
  TReportTableColumn,
} from "@plane/types";
import { ChartXAxisProperty } from "@plane/types";
import { Checkbox, CustomSelect, EModalPosition, EModalWidth, Input, ModalCore, ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import {
  ReportChartError,
  ReportChartLoader,
  ReportQueryConfigForm,
  ReportResultView,
} from "@/components/report-charts";
// hooks
import useDebounce from "@/hooks/use-debounce";
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { WorkspaceDashboardService } from "@/services/workspace-dashboard.service";

const dashboardService = new WorkspaceDashboardService();

const TYPE_ICONS: Record<TDashboardWidgetType, React.ComponentType<{ className?: string }>> = {
  number: Hash,
  bar: BarChart3,
  stacked_bar: Layers,
  line: ChartLine,
  area: ChartArea,
  pie: PieChart,
  donut: ChartPie,
  table: Table2,
};

type Props = {
  workspaceSlug: string;
  dashboardId: string;
  isOpen: boolean;
  onClose: () => void;
  widget?: TDashboardWidget;
};

const defaultForm = (): TDashboardWidgetFormData => ({
  name: "",
  widget_type: "bar",
  size: "medium",
  config: { ...DEFAULT_REPORT_QUERY_CONFIG },
  display: { palette: "modern", show_legend: true },
});

/** Keep a config valid for the chosen widget type. */
const normalizeForType = (type: TDashboardWidgetType, config: TReportQueryConfig): TReportQueryConfig => {
  const definition = DASHBOARD_WIDGET_TYPES.find((d) => d.key === type);
  const next = { ...config };
  if (definition?.requires_dimension && !next.x_axis) next.x_axis = ChartXAxisProperty.STATE_GROUPS;
  if (!definition?.allows_group_by) next.group_by = null;
  if (type === "table") next.table = { columns: next.table?.columns ?? DEFAULT_REPORT_TABLE_COLUMNS, limit: 20 };
  return next;
};

export const DashboardWidgetEditorModal = observer(function DashboardWidgetEditorModal(props: Props) {
  const { workspaceSlug, dashboardId, isOpen, onClose, widget } = props;
  const { t } = useTranslation();
  const { createWidget, updateWidget } = useWorkspaceDashboard();
  const [form, setForm] = useState<TDashboardWidgetFormData>(defaultForm);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setForm(
      widget
        ? {
            name: widget.name,
            widget_type: widget.widget_type,
            size: widget.size,
            config: widget.config,
            display: widget.display,
          }
        : defaultForm()
    );
  }, [isOpen, widget]);

  const typeDefinition = DASHBOARD_WIDGET_TYPES.find((d) => d.key === form.widget_type);
  const previewInput = useDebounce(JSON.stringify({ type: form.widget_type, config: form.config }), 400);
  const {
    data: preview,
    error: previewError,
    isLoading: isPreviewLoading,
    mutate: retryPreview,
  } = useSWR(
    isOpen ? `DASHBOARD_WIDGET_PREVIEW_${workspaceSlug}_${previewInput}` : null,
    () => {
      const { type, config } = JSON.parse(previewInput) as { type: TDashboardWidgetType; config: TReportQueryConfig };
      return dashboardService.previewWidget(workspaceSlug, type, config);
    },
    { revalidateOnFocus: false, keepPreviousData: true }
  );

  const setType = (type: TDashboardWidgetType) => {
    const definition = DASHBOARD_WIDGET_TYPES.find((d) => d.key === type);
    setForm((prev) => ({
      ...prev,
      widget_type: type,
      size: widget ? prev.size : (definition?.default_size ?? prev.size),
      config: normalizeForType(type, prev.config),
    }));
  };

  const toggleColumn = (column: TReportTableColumn) => {
    const columns = form.config.table?.columns ?? DEFAULT_REPORT_TABLE_COLUMNS;
    const next = columns.includes(column) ? columns.filter((c) => c !== column) : [...columns, column];
    if (next.length === 0) return;
    setForm((prev) => ({ ...prev, config: { ...prev.config, table: { ...prev.config.table, columns: next } } }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    const payload = { ...form, config: normalizeForType(form.widget_type, form.config) };
    try {
      if (widget) await updateWidget(workspaceSlug, dashboardId, widget.id, payload);
      else await createWidget(workspaceSlug, dashboardId, payload);
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") });
    } finally {
      setIsSaving(false);
    }
  };

  const paletteLabel = (key: string | undefined) =>
    t(
      CHART_COLOR_PALETTES.find((p) => p.key === (key ?? "modern"))?.i18n_label ??
        "dashboards.widget.color_palettes.modern"
    );
  const sizeLabel = (key: TDashboardWidgetSize) =>
    t(DASHBOARD_WIDGET_SIZES.find((s) => s.key === key)?.i18n_label ?? "dashboards.widget.sizes.medium");

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.VIXL}>
      <div className="flex max-h-[85vh] flex-col">
        <div className="border-b border-subtle px-5 py-4">
          <h3 className="text-18 font-medium text-secondary">
            {widget ? t("dashboards.widget.editor.edit_title") : t("dashboards.widget.editor.create_title")}
          </h3>
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden md:grid-cols-[22rem_1fr]">
          {/* Configuration */}
          <div className="flex flex-col gap-5 overflow-y-auto border-subtle p-5 md:border-r">
            <div className="flex flex-col gap-1.5">
              <span className="text-11 font-medium text-tertiary uppercase">{t("dashboards.widget.editor.name")}</span>
              <Input
                value={form.name}
                onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                placeholder={t("dashboards.widget.editor.name_placeholder")}
                className="w-full text-14"
                maxLength={255}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-11 font-medium text-tertiary uppercase">{t("dashboards.widget.editor.type")}</span>
              <div className="grid grid-cols-4 gap-2">
                {DASHBOARD_WIDGET_TYPES.map((type) => {
                  const Icon = TYPE_ICONS[type.key];
                  return (
                    <button
                      key={type.key}
                      type="button"
                      title={t(type.i18n_label)}
                      onClick={() => setType(type.key)}
                      className={cn(
                        "flex flex-col items-center gap-1 rounded-md border px-1 py-2 text-11 transition-colors",
                        form.widget_type === type.key
                          ? "border-accent-strong bg-accent-primary/10 text-accent-primary"
                          : "border-subtle text-secondary hover:bg-layer-1"
                      )}
                    >
                      <Icon className="size-4" />
                      <span className="line-clamp-1 w-full text-center">{t(type.i18n_label)}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <span className="text-13 font-medium text-primary">{t("dashboards.widget.editor.data")}</span>
              <ReportQueryConfigForm
                workspaceSlug={workspaceSlug}
                value={form.config}
                onChange={(config) =>
                  setForm((prev) => ({ ...prev, config: normalizeForType(prev.widget_type, config) }))
                }
                showDimension={Boolean(typeDefinition?.requires_dimension)}
                requireDimension={Boolean(typeDefinition?.requires_dimension)}
                allowGroupBy={Boolean(typeDefinition?.allows_group_by)}
              />
            </div>

            {form.widget_type === "table" && (
              <div className="flex flex-col gap-1.5">
                <span className="text-11 font-medium text-tertiary uppercase">{t("reports.builder.work_items")}</span>
                <div className="grid grid-cols-2 gap-1.5">
                  {REPORT_TABLE_COLUMNS.map((column) => (
                    <label key={column.key} className="flex cursor-pointer items-center gap-2 text-13 text-secondary">
                      <Checkbox
                        checked={(form.config.table?.columns ?? DEFAULT_REPORT_TABLE_COLUMNS).includes(column.key)}
                        onChange={() => toggleColumn(column.key)}
                      />
                      {t(column.i18n_label)}
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <span className="text-13 font-medium text-primary">{t("dashboards.widget.editor.appearance")}</span>
              <div className="flex flex-col gap-1.5">
                <span className="text-11 font-medium text-tertiary uppercase">
                  {t("dashboards.widget.sizes.label")}
                </span>
                <CustomSelect
                  value={form.size}
                  label={sizeLabel(form.size)}
                  onChange={(size: TDashboardWidgetSize) => setForm((prev) => ({ ...prev, size }))}
                  buttonClassName="w-full justify-between"
                >
                  {DASHBOARD_WIDGET_SIZES.map((size) => (
                    <CustomSelect.Option key={size.key} value={size.key}>
                      {t(size.i18n_label)}
                    </CustomSelect.Option>
                  ))}
                </CustomSelect>
              </div>
              {form.widget_type !== "number" && form.widget_type !== "table" && (
                <>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-11 font-medium text-tertiary uppercase">
                      {t("dashboards.widget.editor.palette")}
                    </span>
                    <CustomSelect
                      value={form.display.palette ?? "modern"}
                      label={paletteLabel(form.display.palette)}
                      onChange={(palette: "modern" | "horizon" | "earthen") =>
                        setForm((prev) => ({ ...prev, display: { ...prev.display, palette } }))
                      }
                      buttonClassName="w-full justify-between"
                    >
                      {CHART_COLOR_PALETTES.map((palette) => (
                        <CustomSelect.Option key={palette.key} value={palette.key}>
                          <span className="flex items-center gap-2">
                            <span className="flex">
                              {palette.light.slice(0, 5).map((color) => (
                                <span key={color} className="size-3" style={{ backgroundColor: color }} />
                              ))}
                            </span>
                            {t(palette.i18n_label)}
                          </span>
                        </CustomSelect.Option>
                      ))}
                    </CustomSelect>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-13 text-secondary">{t("dashboards.widget.editor.show_legend")}</span>
                    <ToggleSwitch
                      value={form.display.show_legend !== false}
                      onChange={(show_legend) =>
                        setForm((prev) => ({ ...prev, display: { ...prev.display, show_legend } }))
                      }
                    />
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Preview */}
          <div className="flex min-h-[22rem] flex-col gap-3 overflow-hidden bg-layer-1 p-5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-13 font-medium text-primary">{t("dashboards.widget.editor.preview")}</span>
              <span className="text-11 text-tertiary">{t("dashboards.widget.editor.preview_hint")}</span>
            </div>
            <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-subtle bg-surface-1 p-4">
              <span className="mb-2 line-clamp-1 text-14 font-medium text-primary">
                {form.name || t("dashboards.widget.untitled")}
              </span>
              <div className="min-h-[16rem] flex-1">
                {isPreviewLoading && !preview ? (
                  <ReportChartLoader />
                ) : previewError ? (
                  <ReportChartError error={previewError} onRetry={() => retryPreview()} />
                ) : preview ? (
                  <ReportResultView
                    workspaceSlug={workspaceSlug}
                    widgetType={form.widget_type}
                    result={preview}
                    config={form.config}
                    display={form.display}
                    compact={false}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-4">
          <Button variant="secondary" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button variant="primary" onClick={handleSave} loading={isSaving}>
            {isSaving
              ? t("dashboards.widget.editor.saving")
              : widget
                ? t("dashboards.widget.editor.update")
                : t("dashboards.widget.editor.save")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
});
