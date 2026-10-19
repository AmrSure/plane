/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TCycleReport,
  TCycleReportSection,
  TReportExportFormat,
  TReportExportLabels,
  TReportQueryConfig,
  TReportQueryResponse,
  TSavedReport,
} from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/** Save a blob response using the filename sent by the server. */
export const downloadBlobResponse = (data: Blob, contentDisposition: string | undefined, fallbackName: string) => {
  const utf8Match = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i);
  const plainMatch = contentDisposition?.match(/filename="?([^";]+)"?/i);
  const filename = utf8Match ? decodeURIComponent(utf8Match[1]) : (plainMatch?.[1] ?? fallbackName);
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const readBlobError = async (error: { response?: { data?: unknown } }) => {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      return JSON.parse(await data.text());
    } catch {
      return undefined;
    }
  }
  return data;
};

export class WorkspaceReportService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/reports`;
  }

  async list(workspaceSlug: string): Promise<TSavedReport[]> {
    return this.get(`${this.base(workspaceSlug)}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async retrieve(workspaceSlug: string, reportId: string): Promise<TSavedReport> {
    return this.get(`${this.base(workspaceSlug)}/${reportId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: Partial<TSavedReport>): Promise<TSavedReport> {
    return this.post(`${this.base(workspaceSlug)}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, reportId: string, data: Partial<TSavedReport>): Promise<TSavedReport> {
    return this.patch(`${this.base(workspaceSlug)}/${reportId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroy(workspaceSlug: string, reportId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}/${reportId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async query(workspaceSlug: string, config: TReportQueryConfig, includeTable = true): Promise<TReportQueryResponse> {
    return this.post(`${this.base(workspaceSlug)}/query/`, { config, include_table: includeTable })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async exportReport(
    workspaceSlug: string,
    payload: { config: TReportQueryConfig; format: TReportExportFormat; title: string; labels: TReportExportLabels }
  ): Promise<void> {
    return this.post(`${this.base(workspaceSlug)}/export/`, payload, { responseType: "blob" })
      .then((response) => downloadBlobResponse(response.data, response.headers?.["content-disposition"], "report"))
      .catch(async (error) => {
        throw await readBlobError(error);
      });
  }

  async getCycleReport(workspaceSlug: string, projectId: string, cycleId: string): Promise<TCycleReport> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/cycles/${cycleId}/report/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async exportCycleReport(
    workspaceSlug: string,
    projectId: string,
    cycleId: string,
    payload: { format: TReportExportFormat; section?: TCycleReportSection; labels: TReportExportLabels }
  ): Promise<void> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/cycles/${cycleId}/report/export/`,
      payload,
      {
        responseType: "blob",
      }
    )
      .then((response) =>
        downloadBlobResponse(response.data, response.headers?.["content-disposition"], "cycle-report")
      )
      .catch(async (error) => {
        throw await readBlobError(error);
      });
  }
}
