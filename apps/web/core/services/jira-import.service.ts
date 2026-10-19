/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TJiraImport, TJiraImportConfig, TJiraImportDetail } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export type TJiraImportApiError = { error?: string; code?: string };

export class JiraImportService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/jira-imports`;
  }

  async list(workspaceSlug: string): Promise<TJiraImport[]> {
    return this.get(`${this.base(workspaceSlug)}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async retrieve(workspaceSlug: string, importId: string, withOptions = false): Promise<TJiraImportDetail> {
    return this.get(`${this.base(workspaceSlug)}/${importId}/`, withOptions ? { params: { options: "true" } } : {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async upload(workspaceSlug: string, file: File, timezone?: string): Promise<TJiraImportDetail> {
    const formData = new FormData();
    formData.append("file", file);
    if (timezone) formData.append("timezone", timezone);
    return this.post(`${this.base(workspaceSlug)}/`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async start(workspaceSlug: string, importId: string, config: Partial<TJiraImportConfig>): Promise<TJiraImportDetail> {
    return this.post(`${this.base(workspaceSlug)}/${importId}/start/`, config)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async undo(workspaceSlug: string, importId: string): Promise<TJiraImportDetail> {
    return this.post(`${this.base(workspaceSlug)}/${importId}/undo/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroy(workspaceSlug: string, importId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}/${importId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
