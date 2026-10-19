/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TChart } from "@plane/types";
import { cn } from "@plane/utils";

type Props = {
  chart: TChart;
  dimensionLabel: string;
  className?: string;
};

/** Chart data as a table: one row per bucket, one column per segment, plus a total. */
export function ReportPivotTable({ chart, dimensionLabel, className }: Props) {
  const { t, currentLocale } = useTranslation();
  const segments = Object.entries(chart.schema ?? {});
  const format = (value: unknown) =>
    typeof value === "number" ? new Intl.NumberFormat(currentLocale, { maximumFractionDigits: 2 }).format(value) : "";

  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">{dimensionLabel}</TableHead>
            {segments.map(([key, name]) => (
              <TableHead key={key} className="text-right whitespace-nowrap">
                {name}
              </TableHead>
            ))}
            <TableHead className="text-right whitespace-nowrap">{t("reports.builder.total")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {chart.data.map((datum) => (
            <TableRow key={String(datum.key)}>
              <TableCell className="text-13">{String(datum.name)}</TableCell>
              {segments.map(([key]) => (
                <TableCell key={key} className="text-right text-13 tabular-nums">
                  {format(datum[key])}
                </TableCell>
              ))}
              <TableCell className="text-right text-13 font-medium tabular-nums">{format(datum.count)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
