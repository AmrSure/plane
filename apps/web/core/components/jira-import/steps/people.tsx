/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ArrowRight } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TJiraImportConfig, TJiraImportDetail } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";

type Props = {
  detail: TJiraImportDetail;
  config: TJiraImportConfig;
  onChange: (config: TJiraImportConfig) => void;
};

const UNASSIGNED = "__unassigned__";

export function JiraImportPeopleStep(props: Props) {
  const { detail, config, onChange } = props;
  const { t } = useTranslation();
  const members = detail.options?.members ?? [];
  const users = detail.analysis.users;

  const memberOptions = [
    {
      value: UNASSIGNED,
      query: t("importer.people.leave_unassigned"),
      content: <span className="text-tertiary">{t("importer.people.leave_unassigned")}</span>,
    },
    ...members.map((member) => {
      const fullName = `${member.first_name} ${member.last_name}`.trim();
      return {
        value: member.id,
        query: `${member.display_name} ${fullName} ${member.email}`,
        content: (
          <div className="flex min-w-0 flex-col">
            <span className="truncate">{fullName || member.display_name}</span>
            <span className="truncate text-11 text-tertiary">{member.email}</span>
          </div>
        ),
      };
    }),
  ];

  if (users.length === 0) return <p className="text-13 text-tertiary">{t("importer.people.none")}</p>;

  const matched = users.filter((user) => config.user_map[user.id]).length;

  return (
    <div className="space-y-3">
      <p className="text-12 text-tertiary">
        {t("importer.people.hint")} {t("importer.people.matched", { matched, total: users.length })}
      </p>
      <div className="divide-y divide-subtle rounded-md border border-subtle">
        {users.map((user) => {
          const memberId = config.user_map[user.id];
          const member = members.find((m) => m.id === memberId);
          return (
            <div key={user.id} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <div className="min-w-0">
                  <div className="truncate text-13 font-medium text-primary">{user.name}</div>
                  <div className="truncate text-11 text-tertiary">
                    {user.roles.map((role) => t(`importer.people.roles.${role}`)).join(", ")}
                  </div>
                </div>
                <ArrowRight className="ms-auto hidden size-3.5 flex-shrink-0 text-tertiary sm:block" />
              </div>
              <div className="sm:w-72">
                <CustomSearchSelect
                  value={memberId ?? UNASSIGNED}
                  options={memberOptions}
                  onChange={(value: string) =>
                    onChange({
                      ...config,
                      user_map: { ...config.user_map, [user.id]: value === UNASSIGNED ? null : value },
                    })
                  }
                  label={
                    member ? (
                      <span className="truncate">
                        {`${member.first_name} ${member.last_name}`.trim() || member.display_name}
                      </span>
                    ) : (
                      <span className="text-tertiary">{t("importer.people.leave_unassigned")}</span>
                    )
                  }
                  buttonClassName="w-full justify-between"
                  maxHeight="md"
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
