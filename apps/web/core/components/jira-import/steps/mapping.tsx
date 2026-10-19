/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ArrowRight } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { PriorityIcon, StateGroupIcon } from "@plane/propel/icons";
import type { TIssuePriorities, TJiraImportConfig, TJiraImportDetail, TStateGroups } from "@plane/types";
import { CustomSelect } from "@plane/ui";
// local
import { PRIORITIES, STATE_GROUPS, targetProject } from "../helpers";

type Props = {
  detail: TJiraImportDetail;
  config: TJiraImportConfig;
  onChange: (config: TJiraImportConfig) => void;
};

const CREATE_PREFIX = "create:";

export function JiraImportMappingStep(props: Props) {
  const { detail, config, onChange } = props;
  const { t } = useTranslation();
  const project = targetProject(detail, config);
  const states = project?.states ?? [];

  const groupLabel = (group: TStateGroups) => t(`importer.groups.${group}`);

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div>
          <h4 className="text-13 font-medium text-primary">{t("importer.mapping.statuses_title")}</h4>
          <p className="text-12 text-tertiary">{t("importer.mapping.statuses_hint")}</p>
        </div>
        <div className="divide-y divide-subtle rounded-md border border-subtle">
          {detail.analysis.statuses.map((status) => {
            const choice = config.status_map[status.name];
            const value =
              choice?.mode === "existing" ? choice.state_id : `${CREATE_PREFIX}${choice?.group ?? "unstarted"}`;
            const existing = choice?.mode === "existing" ? states.find((s) => s.id === choice.state_id) : undefined;
            const label = existing ? (
              <span className="flex items-center gap-2">
                <StateGroupIcon stateGroup={existing.group} className="size-3.5" />
                {existing.name}
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <StateGroupIcon
                  stateGroup={choice?.mode === "create" ? choice.group : "unstarted"}
                  className="size-3.5"
                />
                {t("importer.mapping.create_state", {
                  name: status.name,
                  group: groupLabel(choice?.mode === "create" ? choice.group : "unstarted"),
                })}
              </span>
            );
            return (
              <div key={status.name} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-2 text-13">
                  <span className="truncate font-medium text-primary">{status.name}</span>
                  <span className="text-12 text-tertiary">{t("importer.common.items", { count: status.count })}</span>
                  <ArrowRight className="ms-auto hidden size-3.5 text-tertiary sm:block" />
                </div>
                <div className="sm:w-72">
                  <CustomSelect
                    value={value}
                    label={label}
                    onChange={(next: string) =>
                      onChange({
                        ...config,
                        status_map: {
                          ...config.status_map,
                          [status.name]: next.startsWith(CREATE_PREFIX)
                            ? { mode: "create", group: next.slice(CREATE_PREFIX.length) as TStateGroups }
                            : { mode: "existing", state_id: next },
                        },
                      })
                    }
                    buttonClassName="w-full justify-between"
                    maxHeight="md"
                  >
                    {states.map((state) => (
                      <CustomSelect.Option key={state.id} value={state.id}>
                        <span className="flex items-center gap-2">
                          <StateGroupIcon stateGroup={state.group} className="size-3.5" />
                          {state.name}
                        </span>
                      </CustomSelect.Option>
                    ))}
                    {STATE_GROUPS.map((group) => (
                      <CustomSelect.Option key={group} value={`${CREATE_PREFIX}${group}`}>
                        <span className="flex items-center gap-2">
                          <StateGroupIcon stateGroup={group} className="size-3.5" />
                          {t("importer.mapping.create_state", { name: status.name, group: groupLabel(group) })}
                        </span>
                      </CustomSelect.Option>
                    ))}
                  </CustomSelect>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-2">
        <h4 className="text-13 font-medium text-primary">{t("importer.mapping.priorities_title")}</h4>
        <div className="divide-y divide-subtle rounded-md border border-subtle">
          {detail.analysis.priorities.map((priority) => {
            const value = config.priority_map[priority.name] ?? "none";
            return (
              <div key={priority.name} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-2 text-13">
                  <span className="truncate font-medium text-primary">
                    {priority.name === "None" ? t("importer.mapping.no_priority") : priority.name}
                  </span>
                  <span className="text-12 text-tertiary">{t("importer.common.items", { count: priority.count })}</span>
                  <ArrowRight className="ms-auto hidden size-3.5 text-tertiary sm:block" />
                </div>
                <div className="sm:w-72">
                  <CustomSelect
                    value={value}
                    label={
                      <span className="flex items-center gap-2">
                        <PriorityIcon priority={value} size={12} />
                        {t(`importer.priorities.${value}`)}
                      </span>
                    }
                    onChange={(next: TIssuePriorities) =>
                      onChange({ ...config, priority_map: { ...config.priority_map, [priority.name]: next } })
                    }
                    buttonClassName="w-full justify-between"
                  >
                    {PRIORITIES.map((option) => (
                      <CustomSelect.Option key={option} value={option}>
                        <span className="flex items-center gap-2">
                          <PriorityIcon priority={option} size={12} />
                          {t(`importer.priorities.${option}`)}
                        </span>
                      </CustomSelect.Option>
                    ))}
                  </CustomSelect>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
