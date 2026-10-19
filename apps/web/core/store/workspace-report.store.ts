/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set, unset } from "lodash-es";
import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type { TSavedReport } from "@plane/types";
// services
import { WorkspaceReportService } from "@/services/workspace-report.service";
// store
import type { CoreRootStore } from "./root.store";

export interface IWorkspaceReportStore {
  reportMap: Record<string, TSavedReport>;
  fetchedWorkspaces: Set<string>;
  currentWorkspaceReportIds: string[] | undefined;
  getReportById: (reportId: string) => TSavedReport | undefined;
  fetchReports: (workspaceSlug: string) => Promise<TSavedReport[]>;
  fetchReport: (workspaceSlug: string, reportId: string) => Promise<TSavedReport>;
  createReport: (workspaceSlug: string, data: Partial<TSavedReport>) => Promise<TSavedReport>;
  updateReport: (workspaceSlug: string, reportId: string, data: Partial<TSavedReport>) => Promise<TSavedReport>;
  deleteReport: (workspaceSlug: string, reportId: string) => Promise<void>;
}

export class WorkspaceReportStore implements IWorkspaceReportStore {
  reportMap: Record<string, TSavedReport> = {};
  fetchedWorkspaces: Set<string> = new Set();
  rootStore;
  service;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      reportMap: observable,
      fetchedWorkspaces: observable,
      currentWorkspaceReportIds: computed,
      fetchReports: action,
      fetchReport: action,
      createReport: action,
      updateReport: action,
      deleteReport: action,
    });
    this.rootStore = _rootStore;
    this.service = new WorkspaceReportService();
  }

  get currentWorkspaceReportIds() {
    const workspace = this.rootStore.workspaceRoot.currentWorkspace;
    if (!workspace || !this.fetchedWorkspaces.has(workspace.slug)) return undefined;
    return Object.values(this.reportMap)
      .filter((report) => report.workspace === workspace.id)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((report) => report.id);
  }

  getReportById = computedFn((reportId: string) => this.reportMap[reportId]);

  fetchReports = async (workspaceSlug: string) => {
    const reports = await this.service.list(workspaceSlug);
    runInAction(() => {
      reports.forEach((report) => set(this.reportMap, [report.id], report));
      this.fetchedWorkspaces.add(workspaceSlug);
    });
    return reports;
  };

  fetchReport = async (workspaceSlug: string, reportId: string) => {
    const report = await this.service.retrieve(workspaceSlug, reportId);
    runInAction(() => set(this.reportMap, [report.id], report));
    return report;
  };

  createReport = async (workspaceSlug: string, data: Partial<TSavedReport>) => {
    const report = await this.service.create(workspaceSlug, data);
    runInAction(() => set(this.reportMap, [report.id], report));
    return report;
  };

  updateReport = async (workspaceSlug: string, reportId: string, data: Partial<TSavedReport>) => {
    const report = await this.service.update(workspaceSlug, reportId, data);
    runInAction(() => set(this.reportMap, [reportId], report));
    return report;
  };

  deleteReport = async (workspaceSlug: string, reportId: string) => {
    await this.service.destroy(workspaceSlug, reportId);
    runInAction(() => unset(this.reportMap, [reportId]));
  };
}
