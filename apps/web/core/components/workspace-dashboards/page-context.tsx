/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createContext, useContext, useMemo, useState } from "react";

type TDashboardPageState = {
  isCreateOpen: boolean;
  setIsCreateOpen: (value: boolean) => void;
  isWidgetEditorOpen: boolean;
  setIsWidgetEditorOpen: (value: boolean) => void;
  isEditingLayout: boolean;
  setIsEditingLayout: (value: boolean) => void;
};

const DashboardPageContext = createContext<TDashboardPageState | undefined>(undefined);

export function DashboardPageProvider({ children }: { children: React.ReactNode }) {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isWidgetEditorOpen, setIsWidgetEditorOpen] = useState(false);
  const [isEditingLayout, setIsEditingLayout] = useState(false);
  const value = useMemo(
    () => ({
      isCreateOpen,
      setIsCreateOpen,
      isWidgetEditorOpen,
      setIsWidgetEditorOpen,
      isEditingLayout,
      setIsEditingLayout,
    }),
    [isCreateOpen, isWidgetEditorOpen, isEditingLayout]
  );
  return <DashboardPageContext.Provider value={value}>{children}</DashboardPageContext.Provider>;
}

export const useDashboardPage = (): TDashboardPageState => {
  const context = useContext(DashboardPageContext);
  if (!context) throw new Error("useDashboardPage must be used within DashboardPageProvider");
  return context;
};
