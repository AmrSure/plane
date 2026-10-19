/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
import { FileChartColumn, Globe, Lock, Search } from "lucide-react";
// plane imports
import { REPORT_DIMENSIONS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { TrashIcon } from "@plane/propel/icons";
import type { TSavedReport } from "@plane/types";
import { CustomMenu, Loader } from "@plane/ui";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useWorkspaceReport } from "@/hooks/store/use-workspace-report";
// local imports
import { DeleteReportModal } from "../modals/delete-report-modal";

const SavedReportListItem = observer(function SavedReportListItem(props: {
  workspaceSlug: string;
  report: TSavedReport;
}) {
  const { workspaceSlug, report } = props;
  const { t } = useTranslation();
  const { getUserDetails } = useMember();
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const dimension = REPORT_DIMENSIONS.find((d) => d.key === report.config.x_axis);

  return (
    <>
      <DeleteReportModal
        workspaceSlug={workspaceSlug}
        report={report}
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
      />
      <div className="group flex items-center gap-3 border-b border-subtle px-6 py-3 hover:bg-layer-1">
        <FileChartColumn className="size-4 flex-shrink-0 text-tertiary" />
        <Link href={`/${workspaceSlug}/reports/${report.id}`} className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-14 font-medium text-primary">{report.name}</span>
          <span className="truncate text-12 text-tertiary">
            {report.description || (dimension ? `${t("reports.builder.dimension")}: ${t(dimension.i18n_label)}` : "")}
          </span>
        </Link>
        <span className="hidden items-center gap-1 text-12 text-tertiary md:flex">
          {report.access === 1 ? <Globe className="size-3.5" /> : <Lock className="size-3.5" />}
          {report.access === 1 ? t("reports.access.workspace") : t("reports.access.private")}
        </span>
        <span className="hidden w-32 truncate text-right text-12 text-tertiary lg:block">
          {report.is_owner ? t("dashboards.list.owned_by_you") : (getUserDetails(report.owned_by)?.display_name ?? "")}
        </span>
        <span className="hidden w-24 text-right text-12 text-tertiary lg:block">
          {renderFormattedDate(report.updated_at)}
        </span>
        {report.is_owner && (
          <CustomMenu ellipsis placement="bottom-end" closeOnSelect>
            <CustomMenu.MenuItem onClick={() => setIsDeleteOpen(true)}>
              <span className="flex items-center gap-2 text-danger-primary">
                <TrashIcon width={14} height={14} />
                {t("reports.delete.title")}
              </span>
            </CustomMenu.MenuItem>
          </CustomMenu>
        )}
      </div>
    </>
  );
});

type Props = {
  workspaceSlug: string;
  onCreate: () => void;
};

export const SavedReportList = observer(function SavedReportList(props: Props) {
  const { workspaceSlug, onCreate } = props;
  const { t } = useTranslation();
  const { fetchReports, currentWorkspaceReportIds, getReportById } = useWorkspaceReport();
  const [search, setSearch] = useState("");

  useSWR(`SAVED_REPORTS_${workspaceSlug}`, () => fetchReports(workspaceSlug), { revalidateOnFocus: false });

  if (!currentWorkspaceReportIds) {
    return (
      <Loader className="space-y-2 p-6">
        {[1, 2, 3].map((item) => (
          <Loader.Item key={item} height="48px" />
        ))}
      </Loader>
    );
  }

  if (currentWorkspaceReportIds.length === 0) {
    return (
      <EmptyStateDetailed
        assetKey="dashboard"
        title={t("reports.list.empty.title")}
        description={t("reports.list.empty.description")}
        actions={[{ label: t("reports.list.empty.cta"), onClick: onCreate, variant: "primary" }]}
      />
    );
  }

  const query = search.trim().toLowerCase();
  const reports = currentWorkspaceReportIds
    .map((id) => getReportById(id))
    .filter((report): report is TSavedReport => Boolean(report))
    .filter((report) => !query || report.name.toLowerCase().includes(query));

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex items-center gap-2 border-b border-subtle px-6 py-2.5">
        <Search className="size-3.5 text-tertiary" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("reports.list.search_placeholder")}
          className="w-full bg-transparent text-13 text-primary outline-none placeholder:text-placeholder"
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {reports.length === 0 ? (
          <p className="p-6 text-13 text-tertiary">{t("reports.list.no_results")}</p>
        ) : (
          reports.map((report) => <SavedReportListItem key={report.id} workspaceSlug={workspaceSlug} report={report} />)
        )}
      </div>
    </div>
  );
});
