/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Download } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TReportExportFormat } from "@plane/types";
import { CustomMenu } from "@plane/ui";
import { cn } from "@plane/utils";

type Props = {
  onExport: (format: TReportExportFormat) => Promise<void>;
  csvLabel?: string;
  xlsxLabel?: string;
  disabled?: boolean;
};

export function ReportExportMenu({ onExport, csvLabel, xlsxLabel, disabled }: Props) {
  const { t } = useTranslation();
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async (format: TReportExportFormat) => {
    setIsExporting(true);
    try {
      await onExport(format);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("reports.export.error") });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <CustomMenu
      disabled={disabled || isExporting}
      placement="bottom-end"
      closeOnSelect
      customButton={
        <span className={cn(getButtonStyling("secondary", "lg"), "gap-1.5", { "opacity-60": isExporting })}>
          <Download className="size-3.5" />
          {t("reports.export.label")}
        </span>
      }
    >
      <CustomMenu.MenuItem onClick={() => handleExport("csv")}>
        {csvLabel ?? t("reports.export.csv")}
      </CustomMenu.MenuItem>
      <CustomMenu.MenuItem onClick={() => handleExport("xlsx")}>
        {xlsxLabel ?? t("reports.export.xlsx")}
      </CustomMenu.MenuItem>
    </CustomMenu>
  );
}
