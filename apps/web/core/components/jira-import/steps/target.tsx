/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TJiraImportConfig, TJiraImportDetail } from "@plane/types";
import { CustomSelect, Input } from "@plane/ui";
import { cn } from "@plane/utils";
// local
import { IDENTIFIER_PATTERN, keepsKeys, statusMapFor } from "../helpers";

type Props = {
  detail: TJiraImportDetail;
  config: TJiraImportConfig;
  onChange: (config: TJiraImportConfig) => void;
};

function Choice(props: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  title: string;
  description: string;
}) {
  const { active, disabled, onClick, title, description } = props;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn("flex-1 rounded-md border px-4 py-3 text-start transition-colors", {
        "border-accent-strong bg-accent-subtle": active,
        "border-subtle hover:bg-layer-1": !active && !disabled,
        "cursor-not-allowed border-subtle opacity-50": disabled,
      })}
    >
      <div className="text-13 font-medium text-primary">{title}</div>
      <div className="mt-0.5 text-12 text-tertiary">{description}</div>
    </button>
  );
}

export function JiraImportTargetStep(props: Props) {
  const { detail, config, onChange } = props;
  const { t } = useTranslation();
  const options = detail.options;
  const analysis = detail.analysis;
  const target = config.target;
  const projects = options?.projects ?? [];
  const jiraProjects = analysis.projects;
  const keepKeys = keepsKeys(detail, config);

  const setTarget = (next: TJiraImportConfig["target"]) => {
    const project = next.mode === "existing" ? projects.find((p) => p.id === next.project_id) : undefined;
    onChange({ ...config, target: next, status_map: statusMapFor(detail, project) });
  };

  const identifierError =
    target.mode === "new" && target.identifier && !IDENTIFIER_PATTERN.test(target.identifier)
      ? t("importer.target.identifier_invalid")
      : null;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 rounded-md bg-layer-1 p-4 text-12 sm:grid-cols-4">
        <div>
          <div className="text-tertiary">{t("importer.target.stats.work_items")}</div>
          <div className="text-16 font-medium text-primary">{analysis.work_item_count}</div>
        </div>
        <div>
          <div className="text-tertiary">{t("importer.target.stats.sprints")}</div>
          <div className="text-16 font-medium text-primary">{analysis.sprints.length}</div>
        </div>
        <div>
          <div className="text-tertiary">{t("importer.target.stats.people")}</div>
          <div className="text-16 font-medium text-primary">{analysis.users.length}</div>
        </div>
        <div>
          <div className="text-tertiary">{t("importer.target.stats.keys")}</div>
          <div className="text-16 font-medium text-primary">
            {jiraProjects[0]?.key}-{analysis.keys.min} … {jiraProjects[0]?.key}-{analysis.keys.max}
          </div>
        </div>
      </div>

      {analysis.warnings.length > 0 && (
        <ul className="space-y-1 rounded-md border border-subtle p-3 text-12 text-secondary">
          {analysis.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-3.5 flex-shrink-0 text-warning-primary" />
              {t(`importer.warnings.${warning}`, { count: analysis.date_errors })}
            </li>
          ))}
        </ul>
      )}

      {jiraProjects.length > 1 && (
        <div className="space-y-1">
          <div className="text-13 font-medium text-primary">{t("importer.target.jira_project")}</div>
          <CustomSelect
            value={target.jira_project}
            label={target.jira_project ?? t("importer.target.jira_project")}
            onChange={(key: string) => {
              const jira = jiraProjects.find((p) => p.key === key);
              onChange({
                ...config,
                target:
                  target.mode === "new"
                    ? { ...target, jira_project: key, name: jira?.name ?? target.name, identifier: key.slice(0, 12) }
                    : { ...target, jira_project: key },
              });
            }}
            buttonClassName="w-full justify-between"
          >
            {jiraProjects.map((project) => (
              <CustomSelect.Option key={project.key} value={project.key}>
                {project.key} · {project.name} ({project.count})
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        <Choice
          active={target.mode === "new"}
          disabled={!options?.can_create_project}
          onClick={() =>
            setTarget({
              mode: "new",
              name: jiraProjects[0]?.name ?? "",
              identifier: options?.suggested_identifier.available ? options.suggested_identifier.identifier : "",
              jira_project: target.jira_project,
            })
          }
          title={t("importer.target.new_project")}
          description={
            options?.can_create_project
              ? t("importer.target.new_project_hint")
              : t("importer.target.new_project_admin_only")
          }
        />
        <Choice
          active={target.mode === "existing"}
          disabled={projects.length === 0}
          onClick={() =>
            projects[0] &&
            setTarget({ mode: "existing", project_id: projects[0].id, jira_project: target.jira_project })
          }
          title={t("importer.target.existing_project")}
          description={projects.length ? t("importer.target.existing_project_hint") : t("importer.target.no_projects")}
        />
      </div>

      {target.mode === "new" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="space-y-1 sm:col-span-2">
            <label htmlFor="jira-import-name" className="text-12 text-secondary">
              {t("importer.target.project_name")}
            </label>
            <Input
              id="jira-import-name"
              value={target.name}
              onChange={(event) => onChange({ ...config, target: { ...target, name: event.target.value } })}
              className="w-full"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="jira-import-identifier" className="text-12 text-secondary">
              {t("importer.target.identifier")}
            </label>
            <Input
              id="jira-import-identifier"
              value={target.identifier}
              hasError={Boolean(identifierError)}
              onChange={(event) =>
                onChange({
                  ...config,
                  target: { ...target, identifier: event.target.value.toUpperCase().replace(/\s/g, "").slice(0, 12) },
                })
              }
              className="w-full"
            />
          </div>
          {identifierError && <p className="text-12 text-danger-primary sm:col-span-3">{identifierError}</p>}
          {!options?.suggested_identifier.available && options?.suggested_identifier.identifier && (
            <p className="text-12 text-tertiary sm:col-span-3">
              {t("importer.target.identifier_taken", { identifier: options.suggested_identifier.identifier })}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <div className="text-12 text-secondary">{t("importer.target.project")}</div>
          <CustomSelect
            value={target.project_id}
            label={projects.find((p) => p.id === target.project_id)?.name ?? t("importer.target.project")}
            onChange={(projectId: string) =>
              setTarget({ mode: "existing", project_id: projectId, jira_project: target.jira_project })
            }
            buttonClassName="w-full justify-between"
            maxHeight="md"
          >
            {projects.map((project) => (
              <CustomSelect.Option key={project.id} value={project.id}>
                <span className="text-tertiary">{project.identifier}</span> {project.name}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>
      )}

      <div
        className={cn("flex items-start gap-2 rounded-md p-3 text-12", {
          "bg-success-subtle text-success-primary": keepKeys,
          "bg-layer-1 text-secondary": !keepKeys,
        })}
      >
        {keepKeys ? (
          <CheckCircle2 className="mt-0.5 size-4 flex-shrink-0" />
        ) : (
          <AlertTriangle className="mt-0.5 size-4 flex-shrink-0" />
        )}
        {keepKeys ? t("importer.target.keys_kept") : t("importer.target.keys_renumbered")}
      </div>
    </div>
  );
}
