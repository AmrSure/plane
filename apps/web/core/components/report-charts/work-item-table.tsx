/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import Link from "next/link";
// plane imports
import { REPORT_TABLE_COLUMNS, REPORT_VALUE_LABELS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@plane/propel/table";
import type { TReportTableColumn, TReportTableRow } from "@plane/types";
import { cn, generateWorkItemLink, renderFormattedDate } from "@plane/utils";

type Props = {
  workspaceSlug: string;
  rows: TReportTableRow[];
  columns: TReportTableColumn[];
  className?: string;
};

const DATE_COLUMNS = new Set<TReportTableColumn>(["start_date", "target_date", "completed_at", "created_at"]);

export function ReportWorkItemTable(props: Props) {
  const { workspaceSlug, rows, columns, className } = props;
  const { t } = useTranslation();
  const headerFor = (column: TReportTableColumn) => {
    const option = REPORT_TABLE_COLUMNS.find((c) => c.key === column);
    return option ? t(option.i18n_label) : column;
  };

  const renderCell = (row: TReportTableRow, column: TReportTableColumn) => {
    const value = row[column as keyof TReportTableRow];
    if (column === "sequence_id") return `${row.project_identifier ?? ""}-${row.sequence_id ?? ""}`;
    if (column === "name") {
      return (
        <Link
          href={generateWorkItemLink({
            workspaceSlug,
            projectId: row.project_id,
            issueId: row.id,
            projectIdentifier: row.project_identifier,
            sequenceId: row.sequence_id,
          })}
          className="line-clamp-1 text-primary hover:underline"
        >
          {row.name}
        </Link>
      );
    }
    if (column === "state_name") {
      return (
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 flex-shrink-0 rounded-full"
            style={{ backgroundColor: row.state_color ?? undefined }}
          />
          {row.state_name}
        </span>
      );
    }
    if ((column === "priority" || column === "state_group") && typeof value === "string" && REPORT_VALUE_LABELS[value])
      return t(REPORT_VALUE_LABELS[value]);
    if (Array.isArray(value)) return value.join(", ");
    if (DATE_COLUMNS.has(column) && typeof value === "string") return renderFormattedDate(value) ?? value;
    return value ?? "";
  };

  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column} className="whitespace-nowrap">
                {headerFor(column)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              {columns.map((column) => (
                <TableCell key={column} className={cn("text-13", column === "name" ? "max-w-80" : "whitespace-nowrap")}>
                  {renderCell(row, column)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
