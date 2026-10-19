/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChartYAxisMetric } from "@plane/types";
import type { TReportNumberResult } from "@plane/types";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";

type Props = {
  result: TReportNumberResult;
  className?: string;
};

export function ReportNumberCard({ result, className }: Props) {
  const { t, currentLocale } = useTranslation();
  const isPoints = result.meta.metric === ChartYAxisMetric.ESTIMATE_POINT_COUNT;
  const formatted = new Intl.NumberFormat(currentLocale, { maximumFractionDigits: 2 }).format(result.value);
  return (
    <div className={cn("flex h-full w-full flex-col justify-center gap-1 px-1", className)}>
      <span className="text-28 leading-tight font-semibold text-primary">{formatted}</span>
      <span className="text-13 text-tertiary">
        {isPoints
          ? t("dashboards.widget.work_items", { count: result.work_item_count })
          : t("reports.metrics.work_item_count")}
      </span>
    </div>
  );
}
