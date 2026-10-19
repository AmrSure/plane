/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
// components
import { PageHead } from "@/components/core/page-title";
import { CycleReport } from "@/components/reports";
// hooks
import { useCycle } from "@/hooks/store/use-cycle";
import type { Route } from "./+types/page";

function CycleReportPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId, cycleId } = params;
  const { t } = useTranslation();
  const { getCycleById } = useCycle();
  const cycle = getCycleById(cycleId);

  return (
    <>
      <PageHead title={cycle ? t("cycle_report.page_title", { cycle: cycle.name }) : t("cycle_report.title")} />
      <CycleReport workspaceSlug={workspaceSlug} projectId={projectId} cycleId={cycleId} />
    </>
  );
}

export default observer(CycleReportPage);
