/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { DASHBOARD_ACCESS_OPTIONS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TWorkspaceDashboard, TWorkspaceDashboardFormData } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, TextArea } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useWorkspaceDashboard } from "@/hooks/store/use-workspace-dashboard";
import { useAppRouter } from "@/hooks/use-app-router";

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  data?: TWorkspaceDashboard;
};

const DEFAULT_VALUES: TWorkspaceDashboardFormData = { name: "", description: "", access: 0 };

export function AccessSelector(props: {
  value: 0 | 1;
  onChange: (value: 0 | 1) => void;
  namespace?: "dashboards" | "reports";
}) {
  const { value, onChange, namespace = "dashboards" } = props;
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {DASHBOARD_ACCESS_OPTIONS.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onChange(option.key)}
          className={cn(
            "flex flex-col gap-0.5 rounded-md border px-3 py-2 text-left transition-colors",
            value === option.key ? "border-accent-strong bg-accent-primary/10" : "border-subtle hover:bg-layer-1"
          )}
        >
          <span className="text-13 font-medium text-primary">
            {t(option.i18n_label.replace("dashboards.", `${namespace}.`))}
          </span>
          <span className="text-11 text-tertiary">
            {t(option.i18n_description.replace("dashboards.", `${namespace}.`))}
          </span>
        </button>
      ))}
    </div>
  );
}

export const CreateUpdateDashboardModal = observer(function CreateUpdateDashboardModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, data } = props;
  const { t } = useTranslation();
  const router = useAppRouter();
  const { createDashboard, updateDashboard } = useWorkspaceDashboard();
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TWorkspaceDashboardFormData>({ defaultValues: DEFAULT_VALUES });

  useEffect(() => {
    if (isOpen) reset(data ? { name: data.name, description: data.description, access: data.access } : DEFAULT_VALUES);
  }, [isOpen, data, reset]);

  const onSubmit = async (formData: TWorkspaceDashboardFormData) => {
    try {
      if (data) {
        await updateDashboard(workspaceSlug, data.id, formData);
        setToast({ type: TOAST_TYPE.SUCCESS, title: t("dashboards.toast.updated") });
      } else {
        const dashboard = await createDashboard(workspaceSlug, formData);
        setToast({ type: TOAST_TYPE.SUCCESS, title: t("dashboards.toast.created") });
        router.push(`/${workspaceSlug}/dashboards/${dashboard.id}`);
      }
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("dashboards.toast.error") });
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.XL}>
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">
            {data ? t("dashboards.form.edit_title") : t("dashboards.form.create_title")}
          </h3>
          <div className="space-y-1">
            <Controller
              control={control}
              name="name"
              rules={{ required: t("dashboards.form.name_required"), maxLength: 255 }}
              render={({ field: { value, onChange, ref } }) => (
                <Input
                  id="dashboard-name"
                  name="name"
                  value={value}
                  onChange={onChange}
                  ref={ref}
                  hasError={Boolean(errors.name)}
                  placeholder={t("dashboards.form.name_placeholder")}
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
                id="dashboard-description"
                name="description"
                value={value}
                onChange={onChange}
                placeholder={t("dashboards.form.description_placeholder")}
                className="min-h-20 w-full resize-none text-14"
              />
            )}
          />
          <div className="space-y-1.5">
            <span className="text-11 font-medium text-tertiary uppercase">{t("dashboards.access.label")}</span>
            <Controller
              control={control}
              name="access"
              render={({ field: { value, onChange } }) => <AccessSelector value={value} onChange={onChange} />}
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-4">
          <Button variant="secondary" type="button" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button variant="primary" type="submit" loading={isSubmitting}>
            {data
              ? isSubmitting
                ? t("dashboards.form.updating")
                : t("dashboards.form.update")
              : isSubmitting
                ? t("dashboards.form.creating")
                : t("dashboards.form.create")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
