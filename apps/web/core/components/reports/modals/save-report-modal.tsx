/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TReportDisplay, TReportQueryConfig, TSavedReport } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, TextArea } from "@plane/ui";
// components
import { AccessSelector } from "@/components/workspace-dashboards";
// hooks
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";

type TFormData = { name: string; description: string; access: 0 | 1 };

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  config: TReportQueryConfig;
  display: TReportDisplay;
  /** When set, edit this report's settings instead of creating a new one. */
  report?: TSavedReport;
  onSaved: (report: TSavedReport) => void;
};

export const SaveReportModal = observer(function SaveReportModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, config, display, report, onSaved } = props;
  const { t } = useTranslation();
  const { createReport, updateReport } = useWorkspaceReport();
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TFormData>({ defaultValues: { name: "", description: "", access: 0 } });

  useEffect(() => {
    if (isOpen)
      reset(
        report
          ? { name: report.name, description: report.description, access: report.access }
          : { name: "", description: "", access: 0 }
      );
  }, [isOpen, report, reset]);

  const onSubmit = async (data: TFormData) => {
    try {
      const saved = report
        ? await updateReport(workspaceSlug, report.id, data)
        : await createReport(workspaceSlug, { ...data, config, display });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("reports.toast.saved") });
      onSaved(saved);
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("reports.toast.error") });
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.XL}>
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">
            {report ? t("reports.save_modal.edit_title") : t("reports.save_modal.title")}
          </h3>
          <div className="space-y-1">
            <Controller
              control={control}
              name="name"
              rules={{ required: t("reports.save_modal.name_required"), maxLength: 255 }}
              render={({ field: { value, onChange, ref } }) => (
                <Input
                  id="report-name"
                  name="name"
                  value={value}
                  onChange={onChange}
                  ref={ref}
                  hasError={Boolean(errors.name)}
                  placeholder={t("reports.save_modal.name_placeholder")}
                  className="w-full text-14"
                />
              )}
            />
            {errors.name && <span className="text-11 text-danger-primary">{errors.name.message}</span>}
          </div>
          <Controller
            control={control}
            name="description"
            render={({ field: { value, onChange } }) => (
              <TextArea
                id="report-description"
                name="description"
                value={value}
                onChange={onChange}
                placeholder={t("reports.save_modal.description")}
                className="min-h-20 w-full resize-none text-14"
              />
            )}
          />
          <div className="space-y-1.5">
            <span className="text-11 font-medium text-tertiary uppercase">{t("reports.save_modal.visibility")}</span>
            <Controller
              control={control}
              name="access"
              render={({ field: { value, onChange } }) => (
                <AccessSelector value={value} onChange={onChange} namespace="reports" />
              )}
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-4">
          <Button variant="secondary" type="button" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button variant="primary" type="submit" loading={isSubmitting}>
            {isSubmitting ? t("reports.save_modal.saving") : t("reports.save_modal.save")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
