/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssuePriorities } from "./issues";
import type { TStateGroups } from "./state";

export type TJiraImportStatus = "uploaded" | "queued" | "running" | "completed" | "failed" | "undoing" | "undone";

export type TJiraImportWarning = "multiple_projects" | "duplicate_keys" | "unparsed_dates";

export type TJiraImportUser = {
  id: string;
  name: string;
  roles: string[];
  count: number;
  suggested_member_id: string | null;
};

export type TJiraImportAnalysis = {
  work_item_count: number;
  projects: { key: string; name: string; count: number }[];
  statuses: { name: string; category: string; count: number; suggested_group: TStateGroups }[];
  priorities: { name: string; count: number; suggested: TIssuePriorities }[];
  issue_types: { name: string; count: number }[];
  labels: { name: string; count: number }[];
  sprints: { name: string; count: number; start: string | null; end: string | null }[];
  epics: { key: string; id: string; summary: string; count: number }[];
  users: TJiraImportUser[];
  link_columns: string[];
  features: {
    comments: boolean;
    attachments: boolean;
    links: boolean;
    story_points: boolean;
    parents: boolean;
    watchers: boolean;
    due_dates: boolean;
    start_dates: boolean;
    descriptions: boolean;
  };
  keys: { min: number; max: number; duplicates: string[] };
  date_errors: number;
  warnings: TJiraImportWarning[];
  timezone?: string;
};

export type TJiraImportOptions = {
  keep_keys: boolean;
  sprints_as_cycles: boolean;
  epics_as_modules: boolean;
  issue_types_as_labels: boolean;
  comments: boolean;
  attachments: boolean;
  watchers: boolean;
  on_existing: "update" | "skip";
};

export type TJiraImportTarget =
  | { mode: "new"; name: string; identifier: string; jira_project?: string | null }
  | { mode: "existing"; project_id: string; jira_project?: string | null };

export type TJiraImportStatusChoice = { mode: "existing"; state_id: string } | { mode: "create"; group: TStateGroups };

export type TJiraImportConfig = {
  target: TJiraImportTarget;
  status_map: Record<string, TJiraImportStatusChoice>;
  priority_map: Record<string, TIssuePriorities>;
  user_map: Record<string, string | null>;
  options: TJiraImportOptions;
};

export type TJiraImportMember = {
  id: string;
  display_name: string;
  first_name: string;
  last_name: string;
  email: string;
  avatar_url: string | null;
  role: number;
};

export type TJiraImportTargetProject = {
  id: string;
  name: string;
  identifier: string;
  can_keep_keys: boolean;
  states: { id: string; name: string; group: TStateGroups }[];
};

export type TJiraImportWizardOptions = {
  can_create_project: boolean;
  suggested_identifier: { identifier: string; available: boolean };
  projects: TJiraImportTargetProject[];
  members: TJiraImportMember[];
  default_options: TJiraImportOptions;
};

export type TJiraImportSummary = Partial<
  Record<
    | "created"
    | "updated"
    | "skipped"
    | "failed"
    | "cycles"
    | "modules"
    | "labels"
    | "states"
    | "comments"
    | "links"
    | "relations",
    number
  >
>;

export type TJiraImportError = { row: number | null; key: string | null; message: string };

export type TJiraImport = {
  id: string;
  status: TJiraImportStatus;
  file_name: string;
  file_size: number;
  project: { id: string; name: string; identifier: string } | null;
  created_project: boolean;
  initiated_by: { id: string; display_name: string } | null;
  work_item_count: number;
  processed: number;
  total: number;
  summary: TJiraImportSummary;
  error_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type TJiraImportDetail = TJiraImport & {
  errors: TJiraImportError[];
  analysis: TJiraImportAnalysis;
  config: Partial<TJiraImportConfig>;
  options?: TJiraImportWizardOptions;
};
