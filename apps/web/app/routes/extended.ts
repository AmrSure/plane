/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RouteConfigEntry } from "@react-router/dev/routes";
import { layout, route } from "@react-router/dev/routes";

/**
 * Routes added on top of the core route tree. mergeRoutes() deep-merges layouts by file path,
 * so parent layouts below must match the core paths exactly.
 */
export const extendedRoutes: RouteConfigEntry[] = [
  layout("./(all)/layout.tsx", [
    layout("./(all)/[workspaceSlug]/layout.tsx", [
      layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
        // Dashboards
        layout("./(all)/[workspaceSlug]/(projects)/dashboards/layout.tsx", [
          route(":workspaceSlug/dashboards", "./(all)/[workspaceSlug]/(projects)/dashboards/page.tsx"),
          route(
            ":workspaceSlug/dashboards/:dashboardId",
            "./(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/page.tsx"
          ),
        ]),

        // Reports
        layout("./(all)/[workspaceSlug]/(projects)/reports/layout.tsx", [
          route(":workspaceSlug/reports", "./(all)/[workspaceSlug]/(projects)/reports/page.tsx"),
          route(":workspaceSlug/reports/new", "./(all)/[workspaceSlug]/(projects)/reports/new/page.tsx"),
          route(":workspaceSlug/reports/:reportId", "./(all)/[workspaceSlug]/(projects)/reports/[reportId]/page.tsx"),
        ]),

        // Cycle report
        layout("./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/layout.tsx", [
          layout("./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/cycles/(report)/layout.tsx", [
            route(
              ":workspaceSlug/projects/:projectId/cycles/:cycleId/report",
              "./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/cycles/(report)/[cycleId]/report/page.tsx"
            ),
          ]),
        ]),
      ]),
    ]),
  ]),
];
