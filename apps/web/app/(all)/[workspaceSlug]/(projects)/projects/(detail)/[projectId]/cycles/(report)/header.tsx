/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { FileChartColumn } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { CycleIcon } from "@plane/propel/icons";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
import { useCycle } from "@/hooks/store/use-cycle";

export const CycleReportHeader = observer(function CycleReportHeader() {
  const { workspaceSlug, projectId, cycleId } = useParams();
  const { t } = useTranslation();
  const { getCycleById, fetchCycleDetails } = useCycle();
  const slug = workspaceSlug?.toString() ?? "";
  const project = projectId?.toString() ?? "";
  const cycle = cycleId?.toString() ?? "";

  useSWR(
    slug && project && cycle ? `CYCLE_REPORT_HEADER_${cycle}` : null,
    () => fetchCycleDetails(slug, project, cycle),
    { revalidateOnFocus: false }
  );
  const cycleDetails = cycle ? getCycleById(cycle) : undefined;

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <CommonProjectBreadcrumbs workspaceSlug={slug} projectId={project} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("cycles")}
                href={`/${slug}/projects/${project}/cycles/`}
                icon={<CycleIcon className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink label={cycleDetails?.name ?? ""} href={`/${slug}/projects/${project}/cycles/${cycle}`} />
            }
          />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("cycle_report.title")}
                icon={<FileChartColumn className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
          />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
});
