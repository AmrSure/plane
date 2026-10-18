"""
Apply the brand in branding/brand.json to the source tree.

    python branding/rebrand.py               # brand the upstream "Plane" source
    python branding/rebrand.py --dry-run     # report what would change in text files

Renaming later: edit brand.json and run again. The previously applied brand is read from
branding/applied.json, so the old name, URLs and emails are mapped to the new ones.
For the cleanest result, restore the upstream source first and re-run on it.

What it changes:
  * Code patches in branding/patches.py: telemetry, billing and upsell removal, support links.
  * The product name in UI text, translations, emails, metadata and docs.
  * Links to the upstream company's sites, socials and repo, and their email addresses.
  * Onboarding seed screenshots hosted by upstream.
  * The logo React components and logo SVGs (geometry in branding/logo.py).
  * Docker project, hostnames, container names and default database / queue credentials.

What it never changes:
  * Copyright, SPDX and license lines. AGPL-3.0 requires keeping them.
  * Internal code identifiers such as the @plane/* packages and the Python module.
  * Database migrations, lockfiles and binary files.

Raster images (favicons, PNG logos, spinners) are produced by generate_assets.py.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logo  # noqa: E402
import patches  # noqa: E402

ROOT = logo.ROOT
BRAND = logo.BRAND
APPLIED = ROOT / "branding" / "applied.json"

TEXT_EXTS = {
    ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".html", ".py", ".css", ".md", ".mdx",
    ".yml", ".yaml", ".txt", ".webmanifest", ".svg", ".sh", ".toml", ".example",
}
TEXT_NAMES = {"Dockerfile", "Caddyfile.ce", "Caddyfile.aio.ce", ".env"}
SKIP_DIRS = {".git", "node_modules", "migrations", "branding", ".turbo", "dist", "build", ".react-router"}
SKIP_FILES = {"LICENSE.txt", "COPYRIGHT.txt", "NOTICE.md", "pnpm-lock.yaml"}
SCAN_ROOTS = ["apps", "packages", ".claude", ".github", "docs", "deployments"]
ROOT_FILES = [
    "AGENTS.md", "package.json", "turbo.json", "setup.sh", "docker-compose.yml",
    "docker-compose-local.yml", "docker-compose-test.yml", ".env.example", ".env",
]

# Lines carrying copyright or license notices are left exactly as they are.
PROTECTED_LINE = re.compile(r"Copyright|SPDX-License|See the LICENSE|Licensed under|Plane Software")

INFRA_FILES = [
    "docker-compose.yml", "docker-compose-local.yml", "docker-compose-test.yml",
    "docker-compose.override.yml", ".env.example", ".env", "apps/api/.env.example",
    "apps/api/.env", "apps/live/.env", "apps/live/.env.example", "apps/proxy/Caddyfile.ce",
    "apps/proxy/Caddyfile.aio.ce", "deployments/demo/seed_demo_data.py",
]


def name_rx(word):
    # ASCII-only boundaries so names next to CJK text are matched, and names right
    # after an escape such as "\nPlane" inside a string literal.
    return re.compile(rf"(?:(?<=\\[ntr])|(?<![A-Za-z0-9_$])){re.escape(word)}(?![A-Za-z0-9_$])")


def build_rules(previous):
    b = BRAND
    name, slug, company, token = b["name"], b["slug"], b["company"], b["header_token"]
    site, docs, support, repo = b["website"], b["docs_url"], b["support_url"], b["repo_url"]
    mail, domain = b["support_email"], b["email_domain"]
    url_tail = r"[^\s\"'`<>)\]\\]*"
    rules = [
        # Upstream screenshots embedded in onboarding seed content
        (re.compile(r"<image-component[^>]*seed_assets[^>]*>\s*</image-component>"), ""),
        # Marketing titles and taglines
        (re.compile(r"Plane \| Simple, extensible, open-source project management tool\.?"), name),
        (re.compile(r"Plane Publish \| Make your Plane boards (?:and roadmaps )?pub(?:l)?ic with (?:just )?one-click\.? ?"), f"{name} | Published projects"),
        (re.compile(r"Plane Publish is a customer feedback management tool built on top of plane\.so"), f"Published projects from {name}"),
        (re.compile(r"built on top of plane\.so"), f"built on top of {name}"),
        # Phrases where the upstream name is not a good fit for a long product name
        (re.compile(r"\bPlane Community Edition\b"), name),
        (re.compile(r"\bPlane Publish\b"), name),
        (re.compile(r"\bPlane AI\b"), "AI"),
        (re.compile(r"\bTeam Plane\b"), company),
        # Header lockup call sites are sized for the upstream logo; fit the brand lockup's wider shape
        (re.compile(r"<PlaneLockup height=\{20\} width=\{95\}"),
         f"<PlaneLockup height={{28}} width={{{round(28 * logo.lockup_width() / logo.LOCKUP_H)}}}"),
        # Webhook headers need a token without spaces
        (re.compile(r"\bX-Plane-"), f"X-{token}-"),
        # Email addresses
        (re.compile(r"\b(help|support|sales|contact)@plane\.so\b"), mail),
        (re.compile(r"\b[\w.+-]+@mailer\.plane\.so\b"), f"noreply@{domain}"),
        (re.compile(r"@(?:project)?plane\.so\b"), f"@{domain}"),
        # Links
        (re.compile(r"https?://media\.docs\.plane\.so/logo" + url_tail), f"{site}/static/logos/Logo.png"),
        (re.compile(r"https?://(?:docs|developers)\.plane\.so" + url_tail), docs),
        (re.compile(r"https?://go\.plane\.so/p-docs" + url_tail), docs),
        (re.compile(r"https?://forum\.plane\.so" + url_tail), support),
        (re.compile(r"https?://(?:www\.)?github\.com/makeplane/plane/blob/[^\s\"')]*LICENSE(?:\.txt)?"),
         "https://www.gnu.org/licenses/agpl-3.0.html"),
        (re.compile(r"https?://(?:www\.)?github\.com/makeplane" + url_tail), repo),
        (re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/planepowers" + url_tail), site),
        (re.compile(r"https?://(?:www\.)?linkedin\.com/company/planepowers" + url_tail), site),
        (re.compile(r"https?://(?:[a-z0-9-]+\.)*plane\.so" + url_tail), site),
        (re.compile(r"\btelemetry\.plane\.(?:so|town)\b"), "collector.example.com"),
        (re.compile(r"\b((?:[a-z0-9-]+\.)*)plane\.town\b"), r"\1example.com"),
        (re.compile(r"\b((?:[a-z0-9-]+\.)*)plane\.so\b"), r"\1" + domain),
        (re.compile(r"\bplanepowers\b"), slug),
        (re.compile(r"\bmakeplane\b"), slug),
        # Lowercase uses of the product name in prose
        (re.compile(r"\b(sign up to|Work in|signed in) plane\b"), rf"\1 {name}"),
        (re.compile(r"\bplane account\b"), f"{name} account"),
        (name_rx("Plane"), name),
    ]
    # A previously applied brand (renames)
    if previous:
        if previous.get("header_token") and previous["header_token"] != token:
            rules.append((re.compile(rf"\bX-{re.escape(previous['header_token'])}-"), f"X-{token}-"))
        for key in ("website", "docs_url", "support_url", "repo_url", "support_email"):
            old = previous.get(key, "")
            if old and old != b[key] and "localhost" not in old and "example.com" not in old:
                rules.append((re.compile(re.escape(old)), b[key]))
        old_dom = previous.get("email_domain", "")
        if old_dom and old_dom != domain and old_dom != "example.com":
            rules.append((re.compile(rf"@{re.escape(old_dom)}\b"), f"@{domain}"))
        for key in ("name", "company"):
            old = previous.get(key, "")
            if old and old != b[key]:
                rules.append((name_rx(old), b[key]))
    return rules


def iter_files():
    for rel in ROOT_FILES:
        p = ROOT / rel
        if p.is_file():
            yield p
    for top in SCAN_ROOTS:
        base = ROOT / top
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.name in SKIP_FILES:
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
                continue
            if p.suffix in TEXT_EXTS or p.name in TEXT_NAMES or p.name.startswith("Dockerfile"):
                yield p


def apply_rules(text, rules):
    out = []
    for line in text.splitlines(keepends=True):
        if not PROTECTED_LINE.search(line):
            for pattern, repl in rules:
                line = pattern.sub(repl, line)
        out.append(line)
    return "".join(out)


def rebrand_text(rules, dry_run):
    changed = 0
    for p in iter_files():
        try:
            text = p.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = apply_rules(text, rules)
        if new != text:
            changed += 1
            if not dry_run:
                p.write_bytes(new.encode("utf-8"))
    return changed


HEADER = """/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Modified: brand artwork generated by branding/rebrand.py.
 */

import * as React from "react";

"""


def _svg_component(fn, default_w, default_h, viewbox, body, wrapper=False):
    if wrapper:
        return (
            HEADER + 'import { IconWrapper } from "../icon-wrapper";\nimport type { ISvgIcons } from "../type";\n\n'
            f'export function {fn}({{ color = "currentColor", ...rest }}: ISvgIcons) {{\n'
            "  return (\n"
            f'    <IconWrapper color={{color}} viewBox="{viewbox}" {{...rest}}>\n'
            + "".join(f"      {e}\n" for e in body)
            + "    </IconWrapper>\n  );\n}\n"
        )
    return (
        HEADER + 'import type { ISvgIcons } from "../type";\n\n'
        f'export function {fn}({{ width = "{default_w}", height = "{default_h}", className, color = "currentColor" }}: ISvgIcons) {{\n'
        "  return (\n"
        f'    <svg width={{width}} height={{height}} viewBox="{viewbox}" fill="none" xmlns="http://www.w3.org/2000/svg" className={{className}}>\n'
        + "".join(f"      {e}\n" for e in body)
        + "    </svg>\n  );\n}\n"
    )


def logo_files():
    icons = ROOT / "packages/propel/src/icons"
    wm_vb = logo.viewbox(logo.BBOX_WORDMARK)
    _, _, ww, wh = logo.BBOX_WORDMARK
    ix, iy, iw, ih = logo.BBOX_ICON
    side = ih * 1.1
    icon_vb = f"{ix + iw / 2 - side / 2:.2f} {iy + ih / 2 - side / 2:.2f} {side:.2f} {side:.2f}"
    lw = logo.lockup_width()
    files = {
        # Wordmark is used where the upstream mark was shown
        icons / "brand/plane-logo.tsx": _svg_component(
            "PlaneLogo", round(ww / 4), round(wh / 4), wm_vb, logo.fragment(logo.WORDMARK, "color", jsx=True)),
        icons / "brand/plane-wordmark.tsx": _svg_component(
            "PlaneWordmark", round(ww / 4), round(wh / 4), wm_vb, logo.fragment(logo.WORDMARK, "color", jsx=True)),
        icons / "brand/plane-lockup.tsx": _svg_component(
            "PlaneLockup", round(lw * 20 / logo.LOCKUP_H), 20, f"0 0 {lw} {logo.LOCKUP_H}", logo.lockup_parts("color", jsx=True)),
        icons / "sub-brand/plane-icon.tsx": _svg_component(
            "PlaneNewIcon", 16, 16, icon_vb, logo.fragment(logo.ICON, "color", jsx=True), wrapper=True),
        ROOT / "packages/propel/public/plane-lockup-light.svg": logo.lockup_svg("#FFFFFF") + "\n",
        ROOT / "apps/space/app/assets/plane-logo.svg": logo.icon_svg() + "\n",
        ROOT / "branding/sgt/logo-lockup.svg": logo.lockup_svg() + "\n",
        ROOT / "branding/sgt/logo-icon.svg": logo.icon_svg() + "\n",
    }
    for p in ROOT.glob("apps/*/app/assets/plane-logos/white-horizontal.svg"):
        files[p] = logo.lockup_svg("#FFFFFF") + "\n"
    return files


def write_logos(dry_run):
    files = logo_files()
    if not dry_run:
        for p, content in files.items():
            p.write_text(content, encoding="utf-8", newline="\n")
    return len(files)


def rebrand_infra(old_slugs, dry_run):
    slug = BRAND["slug"]
    host_rule = re.compile(r"\bplane-(db|redis|mq|minio|live|migrator)\b")
    cred_rule = re.compile(
        r'^((?:POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB|RABBITMQ_USER|RABBITMQ_PASSWORD|RABBITMQ_VHOST)=)"?(?:'
        + "|".join(re.escape(s) for s in old_slugs)
        + r')"?\s*$',
        re.M,
    )
    changed = 0
    for rel in INFRA_FILES:
        p = ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        new = host_rule.sub(r"\1", text)
        new = cred_rule.sub(rf'\1"{slug}"', new)
        for old in old_slugs:
            new = re.sub(rf"\b{re.escape(old)}_proxy\b", f"{slug}_proxy", new)
        if rel.startswith("docker-compose"):
            # Prefix container names with the slug so they don't clash with other stacks
            olds = "|".join(re.escape(s) for s in old_slugs + [slug])
            new = re.sub(rf"(container_name:\s*)(?:(?:{olds})-)?(\S+)", rf"\1{slug}-\2", new)
        if rel == "docker-compose.yml":
            if re.search(r"^name:", new, re.M):
                new = re.sub(r"^name:.*$", f"name: {slug}", new, count=1, flags=re.M)
            else:
                new = f"name: {slug}\n\n" + new
        if new != text:
            changed += 1
            if not dry_run:
                p.write_text(new, encoding="utf-8", newline="")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-slug", dest="old_slug", help="previously applied slug, if applied.json is missing")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    previous = json.loads(APPLIED.read_text(encoding="utf-8")) if APPLIED.exists() else {}
    old_slugs = ["plane"] + [s for s in {previous.get("slug"), args.old_slug} if s and s != BRAND["slug"]]

    if not args.dry_run:
        count, failures = patches.apply_all()
        print(f"code patches: {count - len(failures)} applied or already in place")
        for f in failures:
            print(f"  PATCH FAILED {f}")
    print(f"text files changed: {rebrand_text(build_rules(previous), args.dry_run)}")
    if not args.dry_run:
        patches.manifests()
    print(f"logo files written: {write_logos(args.dry_run)}")
    print(f"infra files changed: {rebrand_infra(old_slugs, args.dry_run)}")
    if args.dry_run:
        print("dry run: nothing was written")
    else:
        APPLIED.write_text(json.dumps(BRAND, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
