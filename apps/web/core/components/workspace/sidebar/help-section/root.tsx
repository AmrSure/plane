/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Modified: commercial and upstream-service features removed by branding/patches.py.
 */

import React, { useState } from "react";
import { observer } from "mobx-react";
import { HelpCircle, User } from "lucide-react";
import { useTranslation } from "@plane/i18n";
// ui
import { CustomMenu } from "@plane/ui";
// components
import { AppSidebarItem } from "@/components/sidebar/sidebar-item";
import { PlaneVersionNumber } from "@/components/global/version-number";
// hooks
import { usePowerK } from "@/hooks/store/use-power-k";

const SUPPORT_EMAIL = "info@sure.com.sa";

export const HelpMenuRoot = observer(function HelpMenuRoot() {
  // store hooks
  const { t } = useTranslation();
  const { toggleShortcutsListModal } = usePowerK();
  // states
  const [isNeedHelpOpen, setIsNeedHelpOpen] = useState(false);

  return (
    <CustomMenu
      customButton={
        <AppSidebarItem
          variant="button"
          item={{
            icon: <HelpCircle className="size-5" />,
            isActive: isNeedHelpOpen,
          }}
        />
      }
      menuButtonOnClick={() => !isNeedHelpOpen && setIsNeedHelpOpen(true)}
      onMenuClose={() => setIsNeedHelpOpen(false)}
      placement="bottom-end"
      maxHeight="lg"
      closeOnSelect
    >
      <CustomMenu.MenuItem onClick={() => window.open(`mailto:${SUPPORT_EMAIL}`, "_blank")}>
        <div className="flex items-center gap-x-2 rounded-sm text-11">
          <User className="h-3.5 w-3.5 text-secondary" size={14} />
          <span className="text-11">{t("support")}</span>
        </div>
      </CustomMenu.MenuItem>
      <div className="my-1 border-t border-subtle" />
      <CustomMenu.MenuItem>
        <button
          type="button"
          onClick={() => toggleShortcutsListModal(true)}
          className="flex w-full items-center hover:bg-layer-1"
        >
          <span className="text-11">{t("keyboard_shortcuts")}</span>
        </button>
      </CustomMenu.MenuItem>
      <div className="mt-1 border-t border-subtle px-1 pt-2 text-11 text-secondary">
        <PlaneVersionNumber />
      </div>
    </CustomMenu>
  );
});
