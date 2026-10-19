/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TIssuePriorities,
  TJiraImportConfig,
  TJiraImportDetail,
  TJiraImportStatus,
  TJiraImportStatusChoice,
  TJiraImportTargetProject,
  TStateGroups,
} from "@plane/types";

export const STATE_GROUPS: TStateGroups[] = ["backlog", "unstarted", "started", "completed", "cancelled"];
export const PRIORITIES: TIssuePriorities[] = ["urgent", "high", "medium", "low", "none"];
export const ACTIVE_STATUSES: TJiraImportStatus[] = ["queued", "running", "undoing"];
export const IDENTIFIER_PATTERN = /^[A-Z0-9]{1,12}$/;

export const formatBytes = (size: number) =>
  size >= 1024 * 1024 ? `${(size / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB`;

/** Map each Jira status to a same-named state in the target project, else create one in the suggested group. */
export const statusMapFor = (
  detail: TJiraImportDetail,
  project: TJiraImportTargetProject | undefined
): Record<string, TJiraImportStatusChoice> => {
  const map: Record<string, TJiraImportStatusChoice> = {};
  for (const status of detail.analysis.statuses) {
    const match = project?.states.find((state) => state.name.trim().toLowerCase() === status.name.trim().toLowerCase());
    map[status.name] = match
      ? { mode: "existing", state_id: match.id }
      : { mode: "create", group: status.suggested_group };
  }
  return map;
};

export const initialConfig = (detail: TJiraImportDetail): TJiraImportConfig => {
  const options = detail.options;
  const jiraProject = detail.analysis.projects[0];
  const suggested = options?.suggested_identifier;
  const canCreate = Boolean(options?.can_create_project);
  const firstProject = options?.projects[0];

  const target: TJiraImportConfig["target"] =
    canCreate || !firstProject
      ? {
          mode: "new",
          name: jiraProject?.name ?? "",
          identifier: suggested?.available ? suggested.identifier : "",
          jira_project: jiraProject?.key ?? null,
        }
      : { mode: "existing", project_id: firstProject.id, jira_project: jiraProject?.key ?? null };

  return {
    target,
    status_map: statusMapFor(detail, target.mode === "existing" ? firstProject : undefined),
    priority_map: Object.fromEntries(detail.analysis.priorities.map((p) => [p.name, p.suggested])),
    user_map: Object.fromEntries(detail.analysis.users.map((user) => [user.id, user.suggested_member_id ?? null])),
    options: {
      keep_keys: true,
      sprints_as_cycles: true,
      epics_as_modules: true,
      issue_types_as_labels: true,
      comments: true,
      attachments: true,
      watchers: true,
      on_existing: "update",
      ...options?.default_options,
    },
  };
};

export const targetProject = (detail: TJiraImportDetail, config: TJiraImportConfig) =>
  config.target.mode === "existing"
    ? detail.options?.projects.find((project) => project.id === (config.target as { project_id: string }).project_id)
    : undefined;

/** Jira keys can be kept in a new project, or an existing one with no work items of its own. */
export const keepsKeys = (detail: TJiraImportDetail, config: TJiraImportConfig) =>
  config.target.mode === "new" || Boolean(targetProject(detail, config)?.can_keep_keys);
