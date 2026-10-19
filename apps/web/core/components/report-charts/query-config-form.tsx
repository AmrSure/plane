/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import {
  REPORT_DATE_DIMENSIONS,
  REPORT_DATE_FIELDS,
  REPORT_DATE_GROUPINGS,
  REPORT_DATE_PRESETS,
  REPORT_DIMENSIONS,
  REPORT_METRICS,
} from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type {
  TReportDateField,
  TReportDateGrouping,
  TReportDatePreset,
  TReportDimension,
  TReportMetric,
  TReportQueryConfig,
} from "@plane/types";
import { CustomSelect, ToggleSwitch } from "@plane/ui";
import { getDate, renderFormattedPayloadDate } from "@plane/utils";
// components
import { DateRangeDropdown } from "@/components/dropdowns/date-range";
// local imports
import { ReportStructuredFilters } from "./structured-filters";

type Props = {
  workspaceSlug: string;
  value: TReportQueryConfig;
  onChange: (value: TReportQueryConfig) => void;
  showDimension?: boolean;
  requireDimension?: boolean;
  allowGroupBy?: boolean;
  showFilters?: boolean;
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-11 font-medium text-tertiary uppercase">{label}</span>
      {children}
    </div>
  );
}

const NONE = "__none__";

export const ReportQueryConfigForm = observer(function ReportQueryConfigForm(props: Props) {
  const {
    workspaceSlug,
    value,
    onChange,
    showDimension = true,
    requireDimension = true,
    allowGroupBy = true,
    showFilters = true,
  } = props;
  const { t } = useTranslation();

  const labelOf = (options: { key: string; i18n_label: string }[], key: string | null | undefined) => {
    const option = options.find((o) => o.key === key);
    return option ? t(option.i18n_label) : t("reports.builder.none");
  };
  const usesDateAxis =
    REPORT_DATE_DIMENSIONS.includes(value.x_axis as TReportDimension) ||
    REPORT_DATE_DIMENSIONS.includes(value.group_by as TReportDimension);

  const update = (patch: Partial<TReportQueryConfig>) => {
    const next = { ...value, ...patch };
    const dateAxis =
      REPORT_DATE_DIMENSIONS.includes(next.x_axis as TReportDimension) ||
      REPORT_DATE_DIMENSIONS.includes(next.group_by as TReportDimension);
    next.date_grouping = dateAxis ? (next.date_grouping ?? "MONTH") : null;
    if (next.group_by && next.group_by === next.x_axis) next.group_by = null;
    onChange(next);
  };

  const preset = value.date_range ? (value.date_range.preset ?? "custom") : NONE;

  return (
    <div className="flex flex-col gap-4">
      <Field label={t("reports.builder.metric")}>
        <CustomSelect
          value={value.metric}
          label={labelOf(REPORT_METRICS, value.metric)}
          onChange={(metric: TReportMetric) => update({ metric })}
          buttonClassName="w-full justify-between"
          maxHeight="lg"
        >
          {REPORT_METRICS.map((metric) => (
            <CustomSelect.Option key={metric.key} value={metric.key}>
              {t(metric.i18n_label)}
            </CustomSelect.Option>
          ))}
        </CustomSelect>
      </Field>

      {showDimension && (
        <Field label={t("reports.builder.dimension")}>
          <CustomSelect
            value={value.x_axis ?? NONE}
            label={labelOf(REPORT_DIMENSIONS, value.x_axis)}
            onChange={(key: string) => update({ x_axis: key === NONE ? null : (key as TReportDimension) })}
            buttonClassName="w-full justify-between"
            maxHeight="lg"
          >
            {!requireDimension && <CustomSelect.Option value={NONE}>{t("reports.builder.none")}</CustomSelect.Option>}
            {REPORT_DIMENSIONS.map((dimension) => (
              <CustomSelect.Option key={dimension.key} value={dimension.key}>
                {t(dimension.i18n_label)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </Field>
      )}

      {showDimension && allowGroupBy && value.x_axis && (
        <Field label={t("reports.builder.group_by")}>
          <CustomSelect
            value={value.group_by ?? NONE}
            label={labelOf(REPORT_DIMENSIONS, value.group_by)}
            onChange={(key: string) => update({ group_by: key === NONE ? null : (key as TReportDimension) })}
            buttonClassName="w-full justify-between"
            maxHeight="lg"
          >
            <CustomSelect.Option value={NONE}>{t("reports.builder.none")}</CustomSelect.Option>
            {REPORT_DIMENSIONS.filter((dimension) => dimension.key !== value.x_axis).map((dimension) => (
              <CustomSelect.Option key={dimension.key} value={dimension.key}>
                {t(dimension.i18n_label)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </Field>
      )}

      {showDimension && usesDateAxis && (
        <Field label={t("reports.builder.date_grouping")}>
          <CustomSelect
            value={value.date_grouping ?? "MONTH"}
            label={labelOf(REPORT_DATE_GROUPINGS, value.date_grouping ?? "MONTH")}
            onChange={(date_grouping: TReportDateGrouping) => update({ date_grouping })}
            buttonClassName="w-full justify-between"
          >
            {REPORT_DATE_GROUPINGS.map((grouping) => (
              <CustomSelect.Option key={grouping.key} value={grouping.key}>
                {t(grouping.i18n_label)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </Field>
      )}

      <Field label={t("reports.builder.date_range")}>
        <div className="flex flex-col gap-2">
          <CustomSelect
            value={preset}
            label={preset === NONE ? t("reports.builder.all_time") : labelOf(REPORT_DATE_PRESETS, preset)}
            onChange={(key: string) =>
              update({
                date_range:
                  key === NONE
                    ? null
                    : {
                        field: value.date_range?.field ?? "created_at",
                        preset: key as TReportDatePreset,
                        start: key === "custom" ? (value.date_range?.start ?? null) : null,
                        end: key === "custom" ? (value.date_range?.end ?? null) : null,
                      },
              })
            }
            buttonClassName="w-full justify-between"
            maxHeight="lg"
          >
            <CustomSelect.Option value={NONE}>{t("reports.builder.all_time")}</CustomSelect.Option>
            {REPORT_DATE_PRESETS.map((option) => (
              <CustomSelect.Option key={option.key} value={option.key}>
                {t(option.i18n_label)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
          {value.date_range && (
            <CustomSelect
              value={value.date_range.field}
              label={`${t("reports.builder.date_field")}: ${labelOf(REPORT_DATE_FIELDS, value.date_range.field)}`}
              onChange={(field: TReportDateField) =>
                value.date_range && update({ date_range: { ...value.date_range, field } })
              }
              buttonClassName="w-full justify-between"
            >
              {REPORT_DATE_FIELDS.map((field) => (
                <CustomSelect.Option key={field.key} value={field.key}>
                  {t(field.i18n_label)}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          )}
          {value.date_range?.preset === "custom" && (
            <DateRangeDropdown
              buttonVariant="border-with-text"
              buttonContainerClassName="w-full"
              buttonClassName="w-full"
              value={{ from: getDate(value.date_range.start), to: getDate(value.date_range.end) }}
              onSelect={(range) =>
                value.date_range &&
                update({
                  date_range: {
                    ...value.date_range,
                    start: renderFormattedPayloadDate(range?.from) ?? null,
                    end: renderFormattedPayloadDate(range?.to) ?? null,
                  },
                })
              }
              placeholder={{ from: t("reports.builder.start_date"), to: t("reports.builder.end_date") }}
              isClearable
              mergeDates
            />
          )}
        </div>
      </Field>

      <div className="flex items-center justify-between gap-2">
        <span className="text-13 text-secondary">{t("reports.builder.include_sub_work_items")}</span>
        <ToggleSwitch
          value={value.include_sub_work_items !== false}
          onChange={(include_sub_work_items) => update({ include_sub_work_items })}
        />
      </div>

      {showFilters && (
        <Field label={t("reports.builder.filters")}>
          <ReportStructuredFilters workspaceSlug={workspaceSlug} config={value} onChange={onChange} />
        </Field>
      )}
    </div>
  );
});
