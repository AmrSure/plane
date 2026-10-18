"""
Code patches applied by rebrand.py on top of the upstream source.

Each patch is an exact, idempotent edit:
  * already applied  -> skipped
  * target missing   -> reported as a failure, so upstream changes are noticed on upgrade

Groups:
  telemetry  - no default telemetry collector, no upstream release check, telemetry off by default
  commercial - billing, plan upgrades, sales links, customer logos, product-update feed, legal links
  support    - help menus and error pages point to the brand's own support contact
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "branding" / "brand.json").read_text(encoding="utf-8"))

HEADER = (
    "/**\n"
    " * Copyright (c) 2023-present Plane Software, Inc. and contributors\n"
    " * SPDX-License-Identifier: AGPL-3.0-only\n"
    " * See the LICENSE file for details.\n"
    " *\n"
    " * Modified: commercial and upstream-service features removed by branding/patches.py.\n"
    " */\n\n"
)
MARK = "Modified: commercial and upstream-service features removed by branding/patches.py."


def replace(rel, pairs):
    """Apply (old, new) string replacements; each old must occur exactly once unless new is present."""
    p = ROOT / rel
    if not p.exists():
        return f"missing file {rel}"
    s = p.read_text(encoding="utf-8")
    orig = s
    for old, new in pairs:
        # Already applied: the replacement is present, or a deletion's target is gone
        if (new and new in s) or (not new and old not in s):
            continue
        if s.count(old) != 1:
            return f"{rel}: expected one match for {old[:60]!r}, found {s.count(old)}"
        s = s.replace(old, new)
    if s != orig:
        p.write_text(s, encoding="utf-8", newline="")
    return None


def rewrite(rel, body):
    """Replace a whole file with HEADER + body, unless already rewritten."""
    p = ROOT / rel
    if not p.exists():
        return f"missing file {rel}"
    if MARK in p.read_text(encoding="utf-8"):
        return None
    p.write_text(HEADER + body, encoding="utf-8", newline="\n")
    return None


def delete(rel):
    p = ROOT / rel
    if p.is_dir():
        for f in sorted(p.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
        p.rmdir()
    elif p.exists():
        p.unlink()
    return None


def telemetry():
    return [
        replace("apps/api/plane/utils/otlp_endpoints.py", [
            ('_DEFAULT_OTLP_ENDPOINT = "https://telemetry.plane.so"',
             '# No default collector: telemetry is only exported when OTLP_ENDPOINT is set.\n'
             '_DEFAULT_OTLP_ENDPOINT = ""\n\n\n'
             'def is_otlp_configured() -> bool:\n'
             '    """Return True when an OTLP collector endpoint has been configured."""\n'
             '    return bool(os.environ.get("OTLP_ENDPOINT", _DEFAULT_OTLP_ENDPOINT).strip())'),
            ('host = parsed.hostname or "telemetry.plane.so"', 'host = parsed.hostname or "localhost"'),
        ]),
        replace("apps/api/plane/license/bgtasks/telemetry_metrics.py", [
            ("from plane.utils.otlp_endpoints import get_otlp_grpc_endpoint, get_otlp_http_metrics_url\n",
             "from plane.utils.otlp_endpoints import get_otlp_grpc_endpoint, get_otlp_http_metrics_url, is_otlp_configured\n"),
            ('        logger.debug("Telemetry disabled, skipping metrics push")\n        return\n',
             '        logger.debug("Telemetry disabled, skipping metrics push")\n        return\n\n'
             '    if not is_otlp_configured():\n'
             '        logger.debug("No OTLP_ENDPOINT configured, skipping metrics push")\n        return\n'),
        ]),
        replace("apps/api/plane/license/management/commands/register_instance.py", [
            ("import requests\n", ""),
            ("""        try:
            response = requests.get(
                "https://api.github.com/repos/makeplane/plane/releases/latest",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("tag_name", fallback_version)
        except Exception:
            self.stdout.write("Error checking for latest version")
            return fallback_version
""", """        # Upstream release checks are disabled; this build is versioned independently.
        return fallback_version
"""),
            ('                is_test=os.environ.get("IS_TEST", "0") == "1",\n',
             '                is_test=os.environ.get("IS_TEST", "0") == "1",\n                is_telemetry_enabled=False,\n'),
        ]),
        replace("apps/admin/components/instance/setup-form.tsx", [
            ('  password: "",\n  is_telemetry_enabled: true,\n', '  password: "",\n  is_telemetry_enabled: false,\n'),
            ('(searchParams?.get("is_telemetry_enabled") === "True" ? true : false) || true;',
             'searchParams?.get("is_telemetry_enabled") === "True";'),
            ("""                Allow Plane to anonymously collect usage events.{" "}
                <a
                  href="https://developers.plane.so/self-hosting/telemetry"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:text-blue-600 flex-shrink-0 text-13 font-medium"
                >
                  See More
                </a>
""", """                Collect anonymous usage metrics. They are only sent if an OTLP collector is configured.
"""),
        ]),
        # Telemetry description in instance settings
        replace("apps/admin/app/(all)/(dashboard)/general/form.tsx", [
            ("""              <div className="text-13 leading-5 font-medium text-primary">Let Plane collect anonymous usage data</div>
              <div className="text-11 leading-5 font-regular text-tertiary">
                No PII is collected.This anonymized data is used to understand how you use Plane and build new features
                in line with{" "}
                <a
                  href="https://developers.plane.so/self-hosting/telemetry"
                  target="_blank"
                  className="text-accent-primary hover:underline"
                  rel="noreferrer"
                >
                  our Telemetry Policy.
                </a>
              </div>""", """              <div className="text-13 leading-5 font-medium text-primary">Collect anonymous usage metrics</div>
              <div className="text-11 leading-5 font-regular text-tertiary">
                No personal data is collected. Metrics are only sent if an OTLP collector is configured for this
                instance with the OTLP_ENDPOINT setting.
              </div>"""),
        ]),
    ]


def commercial():
    web = "apps/web"
    return [
        # Customer logos under the sign-in form
        rewrite(f"{web}/core/components/auth-screens/footer.tsx",
                "export function AuthFooter() {\n  return null;\n}\n"),
        # "Community" edition button that opens the plan upgrade modal
        rewrite(f"{web}/core/components/workspace/edition-badge.tsx",
                "export function WorkspaceEditionBadge() {\n  return null;\n}\n"),
        # "Pro" badges next to locked features
        rewrite(f"{web}/core/components/workspace/upgrade-badge.tsx",
                "type TUpgradeBadge = {\n  className?: string;\n  size?: \"sm\" | \"md\";\n};\n\n"
                "export function UpgradeBadge(_props: TUpgradeBadge) {\n  return null;\n}\n"),
        # Plan comparison and checkout modal
        rewrite(f"{web}/core/components/license/modal/upgrade-modal.tsx",
                "export type PaidPlanUpgradeModalProps = {\n  isOpen: boolean;\n  handleClose: () => void;\n};\n\n"
                "export function PaidPlanUpgradeModal(_props: PaidPlanUpgradeModalProps) {\n  return null;\n}\n"),
        # Bulk operations upsell banner
        rewrite(f"{web}/core/components/issues/bulk-operations/upgrade-banner.tsx",
                "type Props = {\n  className?: string;\n};\n\n"
                "export function BulkOperationsUpgradeBanner(_props: Props) {\n  return null;\n}\n"),
        # Workspace "Active cycles" page is only an upgrade pitch
        rewrite(f"{web}/core/components/active-cycles/workspace-active-cycles-upgrade.tsx",
                "export function WorkspaceActiveCyclesUpgrade() {\n  return null;\n}\n"),
        replace(f"{web}/app/routes/core.ts", [
            ("""        // Active Cycles
        layout("./(all)/[workspaceSlug]/(projects)/active-cycles/layout.tsx", [
          route(":workspaceSlug/active-cycles", "./(all)/[workspaceSlug]/(projects)/active-cycles/page.tsx"),
        ]),

""", ""),
            ("""          route(
            ":workspaceSlug/settings/billing",
            "./(all)/[workspaceSlug]/(settings)/settings/(workspace)/billing/page.tsx"
          ),
""", ""),
        ]),
        delete(f"{web}/app/(all)/[workspaceSlug]/(projects)/active-cycles"),
        delete(f"{web}/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/billing"),
        # Billing entry in workspace settings
        replace("packages/constants/src/settings/workspace.ts", [
            ('    WORKSPACE_SETTINGS["billing-and-plans"],\n', ""),
        ]),
        # Links to upstream legal pages under the sign-in form
        rewrite(f"{web}/core/components/account/terms-and-conditions.tsx",
                'import type { EAuthModes } from "@plane/constants";\n\n'
                "interface TermsAndConditionsProps {\n  authType?: EAuthModes;\n}\n\n"
                "export function TermsAndConditions(_props: TermsAndConditionsProps) {\n  return null;\n}\n"),
        rewrite("apps/space/components/account/terms-and-conditions.tsx",
                "type Props = {\n  isSignUp?: boolean;\n};\n\n"
                "export function TermsAndConditions(_props: Props) {\n  return null;\n}\n"),
        # "Star us on GitHub" in the top navigation
        rewrite(f"{web}/app/(all)/[workspaceSlug]/(projects)/star-us-link.tsx",
                "export function StarUsOnGitHubLink() {\n  return null;\n}\n"),
        # Community promotion on the expired-invitation page
        replace(f"{web}/app/(all)/workspace-invitations/page.tsx", [
            ('import { Boxes, Share2, Star, User2 } from "lucide-react";', 'import { Boxes, User2 } from "lucide-react";'),
            ("""              <EmptySpaceItem Icon={Star} title="Star us on GitHub" href="https://github.com/makeplane" />
              <EmptySpaceItem
                Icon={Share2}
                title="Join our community of active creators"
                href="https://forum.plane.so"
              />
""", ""),
        ]),
        # Status page and social account on the web error page
        replace(f"{web}/app/error/prod.tsx", [
            ("""  {
    key: "status",
    label: "Status Page",
    value: "https://status.plane.so/",
  },
  {
    key: "twitter_handle",
    label: "@planepowers",
    value: "https://x.com/planepowers",
  },
""", ""),
        ]),
    ]


def support():
    email = BRAND["support_email"]
    return [
        # Sidebar help menu: support contact, shortcuts and version only
        rewrite("apps/web/core/components/workspace/sidebar/help-section/root.tsx", f'''import React, {{ useState }} from "react";
import {{ observer }} from "mobx-react";
import {{ HelpCircle, User }} from "lucide-react";
import {{ useTranslation }} from "@plane/i18n";
// ui
import {{ CustomMenu }} from "@plane/ui";
// components
import {{ AppSidebarItem }} from "@/components/sidebar/sidebar-item";
import {{ PlaneVersionNumber }} from "@/components/global/version-number";
// hooks
import {{ usePowerK }} from "@/hooks/store/use-power-k";

const SUPPORT_EMAIL = "{email}";

export const HelpMenuRoot = observer(function HelpMenuRoot() {{
  // store hooks
  const {{ t }} = useTranslation();
  const {{ toggleShortcutsListModal }} = usePowerK();
  // states
  const [isNeedHelpOpen, setIsNeedHelpOpen] = useState(false);

  return (
    <CustomMenu
      customButton={{
        <AppSidebarItem
          variant="button"
          item={{{{
            icon: <HelpCircle className="size-5" />,
            isActive: isNeedHelpOpen,
          }}}}
        />
      }}
      menuButtonOnClick={{() => !isNeedHelpOpen && setIsNeedHelpOpen(true)}}
      onMenuClose={{() => setIsNeedHelpOpen(false)}}
      placement="bottom-end"
      maxHeight="lg"
      closeOnSelect
    >
      <CustomMenu.MenuItem onClick={{() => window.open(`mailto:${{SUPPORT_EMAIL}}`, "_blank")}}>
        <div className="flex items-center gap-x-2 rounded-sm text-11">
          <User className="h-3.5 w-3.5 text-secondary" size={{14}} />
          <span className="text-11">{{t("support")}}</span>
        </div>
      </CustomMenu.MenuItem>
      <div className="my-1 border-t border-subtle" />
      <CustomMenu.MenuItem>
        <button
          type="button"
          onClick={{() => toggleShortcutsListModal(true)}}
          className="flex w-full items-center hover:bg-layer-1"
        >
          <span className="text-11">{{t("keyboard_shortcuts")}}</span>
        </button>
      </CustomMenu.MenuItem>
      <div className="mt-1 border-t border-subtle px-1 pt-2 text-11 text-secondary">
        <PlaneVersionNumber />
      </div>
    </CustomMenu>
  );
}});
'''),
        # Command palette help actions: upstream docs, forum and bug tracker removed
        rewrite("apps/web/core/components/power-k/config/help-commands.ts", '''import { Rocket } from "lucide-react";
// components
import type { TPowerKCommandConfig } from "@/components/power-k/core/types";
// hooks
import { usePowerK } from "@/hooks/store/use-power-k";

export const usePowerKHelpCommands = (): TPowerKCommandConfig[] => {
  // store
  const { toggleShortcutsListModal } = usePowerK();

  return [
    {
      id: "open_keyboard_shortcuts",
      type: "action",
      group: "help",
      i18n_title: "power_k.help_actions.open_keyboard_shortcuts",
      icon: Rocket,
      modifierShortcut: "cmd+/",
      action: () => toggleShortcutsListModal(true),
      isEnabled: () => true,
      isVisible: () => true,
      closeOnSelect: true,
    },
  ];
};
'''),
        # Admin console help menu
        replace("apps/admin/app/(all)/(dashboard)/sidebar-help-section.tsx", [
            ('import { GithubIcon, NewTabIcon, PageIcon } from "@plane/propel/icons";',
             'import { NewTabIcon } from "@plane/propel/icons";'),
            ("""const helpOptions = [
  {
    name: "Documentation",
    href: "https://docs.plane.so/",
    Icon: PageIcon,
  },
  {
    name: "Join our Forum",
    href: "https://forum.plane.so",
    Icon: MessageSquare,
  },
  {
    name: "Report a bug",
    href: "https://github.com/makeplane/plane/issues/new/choose",
    Icon: GithubIcon,
  },
];""", f"""const helpOptions = [
  {{
    name: "Contact support",
    href: "mailto:{email}",
    Icon: MessageSquare,
  }},
];"""),
        ]),
        # Public pages error screen
        replace("apps/space/app/error.tsx", [
            ("""            That crashed Plane, pun intended. No worries, though. Our engineers have been notified. If you have more
            details, please write to{" "}
            <a href="mailto:support@plane.so" className="text-accent-primary">
              support@plane.so
            </a>{" "}
            or on our{" "}
            <a href="https://forum.plane.so" target="_blank" className="text-accent-primary" rel="noopener noreferrer">
              Forum
            </a>
            .""", f"""            Something went wrong and the page could not load. If the problem continues, please write to{{" "}}
            <a href="mailto:{email}" className="text-accent-primary">
              {email}
            </a>
            ."""),
        ]),
    ]


def theme():
    """Shift the UI accent palette (--brand-*) to the brand hue, keeping each step's lightness."""
    rel = "packages/tailwind-config/variables.css"
    p = ROOT / rel
    if not p.exists():
        return [f"missing file {rel}"]
    hue = BRAND.get("theme_hue", 263)
    s = p.read_text(encoding="utf-8")

    def shift(m):
        name, l, c, h = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
        if name == "default":
            return f"--brand-default: {BRAND.get('theme_default', 'oklch(0.5233 0.2659 263.1)')};"
        if h == hue:
            return m.group(0)  # already shifted
        # More saturated, same lightness, brand hue
        return f"--brand-{name}: oklch({l:.4f} {min(c * 1.6, 0.26):.4f} {hue});"

    new = re.sub(r"--brand-(\d+|default): oklch\(([\d.]+) ([\d.]+) ([\d.]+)\);", shift, s)
    if new != s:
        p.write_text(new, encoding="utf-8", newline="")
    return []


def manifests():
    """Set short_name in web app manifests to the brand's short name."""
    errors = []
    for p in list(ROOT.glob("apps/*/public/**/*manifest*")) + list(ROOT.glob("apps/*/app/assets/favicon/*manifest*")) + list(ROOT.glob("apps/web/manifest.json")):
        s = p.read_text(encoding="utf-8")
        new = re.sub(r'("short_name"\s*:\s*)"[^"]*"', rf'\1"{BRAND["short_name"]}"', s)
        if new != s:
            p.write_text(new, encoding="utf-8", newline="")
    return errors


def apply_all():
    results = []
    for group in (telemetry, commercial, support, theme):
        results += [(group.__name__, r) for r in group()]
    failures = [f"[{g}] {r}" for g, r in results if r]
    return len(results), failures
