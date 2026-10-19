/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo } from "react";
import { observer } from "mobx-react";
// plane imports
import { REPORT_VALUE_LABELS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { getButtonStyling } from "@plane/propel/button";
import { ChevronDownIcon } from "@plane/propel/icons";
import type { TReportQueryConfig } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useLabel } from "@/hooks/store/use-label";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
// local imports
import type { TStructuredFilters } from "./utils";
import { fromFilterExpression, toFilterExpression } from "./utils";

type TOption = { value: string; query: string; content: React.ReactNode };

type MultiSelectProps = {
  label: string;
  values: string[];
  options: TOption[];
  onChange: (values: string[]) => void;
  summarize: (values: string[]) => string;
};

function MultiSelectFilter({ label, values, options, onChange, summarize }: MultiSelectProps) {
  return (
    <CustomSearchSelect
      value={values}
      onChange={(next: string[]) => onChange(next)}
      options={options}
      multiple
      className="border-none p-0"
      customButtonClassName="border-none p-0 bg-transparent hover:bg-transparent w-auto h-auto"
      customButton={
        <div className={cn(getButtonStyling("secondary", "lg"), "max-w-64 gap-1.5")}>
          <span className="text-tertiary">{label}</span>
          {values.length > 0 && <span className="truncate text-primary">{summarize(values)}</span>}
          <ChevronDownIcon className="size-3 flex-shrink-0" aria-hidden="true" />
        </div>
      }
    />
  );
}

const nameList = (values: string[], resolve: (value: string) => string | undefined) =>
  values.length > 2 ? `${values.length}` : values.map((value) => resolve(value) ?? value).join(", ");

const STATE_GROUPS = ["backlog", "unstarted", "started", "completed", "cancelled"];
const PRIORITIES = ["urgent", "high", "medium", "low", "none"];

type Props = {
  workspaceSlug: string;
  config: TReportQueryConfig;
  onChange: (config: TReportQueryConfig) => void;
};

export const ReportStructuredFilters = observer(function ReportStructuredFilters(props: Props) {
  const { workspaceSlug, config, onChange } = props;
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();
  const {
    getUserDetails,
    workspace: { workspaceMemberIds },
  } = useMember();
  const { workspaceLabels, fetchWorkspaceLabels } = useLabel();

  useEffect(() => {
    if (!workspaceLabels) fetchWorkspaceLabels(workspaceSlug).catch(() => undefined);
  }, [workspaceSlug, workspaceLabels, fetchWorkspaceLabels]);

  const filters = useMemo(() => fromFilterExpression(config.filters), [config.filters]);
  const setFilter = (key: keyof TStructuredFilters, values: string[]) =>
    onChange({ ...config, filters: toFilterExpression({ ...filters, [key]: values }) });

  const projectOptions: TOption[] = joinedProjectIds.map((id) => {
    const project = getProjectById(id);
    return { value: id, query: `${project?.name} ${project?.identifier}`, content: project?.name ?? id };
  });
  const memberOptions: TOption[] = (workspaceMemberIds ?? []).map((id) => {
    const user = getUserDetails(id);
    return {
      value: id,
      query: `${user?.display_name} ${user?.first_name} ${user?.last_name}`,
      content: user?.display_name ?? id,
    };
  });
  const uniqueLabels = new Map<string, string>();
  (workspaceLabels ?? []).forEach((label) => uniqueLabels.set(label.id, label.name));
  const labelOptions: TOption[] = Array.from(uniqueLabels.entries()).map(([id, name]) => ({
    value: id,
    query: name,
    content: name,
  }));
  const enumOptions = (values: string[]): TOption[] =>
    values.map((value) => ({ value, query: t(REPORT_VALUE_LABELS[value]), content: t(REPORT_VALUE_LABELS[value]) }));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <MultiSelectFilter
        label={t("reports.builder.projects")}
        values={config.project_ids ?? []}
        options={projectOptions}
        onChange={(values) => onChange({ ...config, project_ids: values })}
        summarize={(values) => nameList(values, (id) => getProjectById(id)?.name)}
      />
      <MultiSelectFilter
        label={t("reports.builder.state_groups")}
        values={filters.state_groups}
        options={enumOptions(STATE_GROUPS)}
        onChange={(values) => setFilter("state_groups", values)}
        summarize={(values) => nameList(values, (value) => t(REPORT_VALUE_LABELS[value]))}
      />
      <MultiSelectFilter
        label={t("reports.builder.priorities")}
        values={filters.priorities}
        options={enumOptions(PRIORITIES)}
        onChange={(values) => setFilter("priorities", values)}
        summarize={(values) => nameList(values, (value) => t(REPORT_VALUE_LABELS[value]))}
      />
      <MultiSelectFilter
        label={t("reports.builder.assignees")}
        values={filters.assignee_ids}
        options={memberOptions}
        onChange={(values) => setFilter("assignee_ids", values)}
        summarize={(values) => nameList(values, (id) => getUserDetails(id)?.display_name)}
      />
      <MultiSelectFilter
        label={t("reports.builder.labels")}
        values={filters.label_ids}
        options={labelOptions}
        onChange={(values) => setFilter("label_ids", values)}
        summarize={(values) => nameList(values, (id) => uniqueLabels.get(id))}
      />
    </div>
  );
});
