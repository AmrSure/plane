"""
Apply the brand in branding/brand.json to the source tree.

    python branding/rebrand.py                 # rebrand upstream "Plane" source
    python branding/rebrand.py --from OldName  # rename a previously applied brand
    python branding/rebrand.py --dry-run       # report what would change

What it changes:
  * The product name in UI text, translations, emails, metadata and docs.
  * Links to the upstream company's sites, socials and repo, and their email addresses.
  * Onboarding seed screenshots hosted by upstream.
  * The logo React components and the lockup SVG (artwork from branding/logo.py).
  * Docker hostnames and default database / queue credentials.

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
from logo import mark_path, wordmark_width  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "branding" / "brand.json").read_text(encoding="utf-8"))

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


def build_rules(old_names):
    name, slug = BRAND["name"], BRAND["slug"]
    site, docs, support, repo = BRAND["website"], BRAND["docs_url"], BRAND["support_url"], BRAND["repo_url"]
    mail, domain = BRAND["support_email"], BRAND["email_domain"]
    url_tail = r"[^\s\"'`<>)\]\\]*"
    rules = [
        # Upstream screenshots embedded in onboarding seed content
        (re.compile(r"<image-component[^>]*seed_assets[^>]*>\s*</image-component>"), ""),
        # Phrases where a bare domain was used as a product name
        (re.compile(r"built on top of plane\.so"), f"built on top of {name}"),
        # Email addresses
        (re.compile(r"\b(help|support|sales|contact)@plane\.so\b"), mail),
        (re.compile(r"\b[\w.+-]+@mailer\.plane\.so\b"), f"noreply@{domain}"),
        (re.compile(r"@(?:project)?plane\.so\b"), f"@{domain}"),
        # Links
        (re.compile(r"https?://media\.docs\.plane\.so/logo" + url_tail), f"{site}/static/logos/Logo.png"),
        (re.compile(r"https?://(?:docs|developers)\.plane\.so" + url_tail), docs),
        (re.compile(r"https?://go\.plane\.so/p-docs" + url_tail), docs),
        (re.compile(r"https?://forum\.plane\.so" + url_tail), support),
        (re.compile(r"https?://(?:www\.)?github\.com/makeplane" + url_tail), repo),
        (re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/planepowers" + url_tail), site),
        (re.compile(r"https?://(?:www\.)?linkedin\.com/company/planepowers" + url_tail), site),
        (re.compile(r"https?://(?:[a-z0-9-]+\.)*plane\.so" + url_tail), site),
        (re.compile(r"\b((?:[a-z0-9-]+\.)*)plane\.(?:so|town)\b"), r"\1" + domain),
        (re.compile(r"\bplanepowers\b"), slug),
        (re.compile(r"\bmakeplane\b"), slug),
        # Lowercase uses of the product name in prose
        (re.compile(r"\b(sign up to|Work in|signed in) plane\b"), rf"\1 {name}"),
        (re.compile(r"\bplane account\b"), f"{name} account"),
    ]
    for old in old_names:
        # ASCII-only boundaries so names next to CJK text are matched too
        # and names right after an escape such as "\nPlane" inside a string literal
        rules.append((re.compile(rf"(?:(?<=\\[ntr])|(?<![A-Za-z0-9_$])){re.escape(old)}(?![A-Za-z0-9_$])"), name))
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
            raw = p.read_bytes()
            text = raw.decode("utf-8")
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


def logo_components():
    name = BRAND["name"]
    path = mark_path()
    text_w = wordmark_width(name, 36)
    lock_w = 48 + 12 + wordmark_width(name, 40)
    text = (
        '<text x="{x}" y="{y}" fontFamily="Inter, ui-sans-serif, system-ui, sans-serif" '
        'fontWeight="700" fontSize="{fs}" textLength="{tl}" lengthAdjust="spacingAndGlyphs" '
        'fill={{color}}>\n        {name}\n      </text>'
    )
    icons = ROOT / "packages/propel/src/icons"
    files = {
        icons / "brand/plane-logo.tsx": HEADER + 'import type { ISvgIcons } from "../type";\n\n'
        f'export function PlaneLogo({{ width = "52", height = "52", className, color = "currentColor" }}: ISvgIcons) {{\n'
        "  return (\n"
        '    <svg width={width} height={height} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>\n'
        f'      <path fillRule="evenodd" clipRule="evenodd" d="{path}" fill={{color}} />\n'
        "    </svg>\n  );\n}\n",
        icons / "brand/plane-wordmark.tsx": HEADER + 'import type { ISvgIcons } from "../type";\n\n'
        f'export function PlaneWordmark({{ width = "{text_w}", height = "44", className, color = "currentColor" }}: ISvgIcons) {{\n'
        "  return (\n"
        f'    <svg width={{width}} height={{height}} viewBox="0 0 {text_w} 44" fill="none" xmlns="http://www.w3.org/2000/svg" className={{className}}>\n'
        "      " + text.format(x=0, y=34, fs=36, tl=text_w, name=name) + "\n"
        "    </svg>\n  );\n}\n",
        icons / "brand/plane-lockup.tsx": HEADER + 'import type { ISvgIcons } from "../type";\n\n'
        f'export function PlaneLockup({{ width = "{lock_w}", height = "53", className, color = "currentColor" }}: ISvgIcons) {{\n'
        "  return (\n"
        f'    <svg width={{width}} height={{height}} viewBox="0 0 {lock_w} 53" fill="none" xmlns="http://www.w3.org/2000/svg" className={{className}}>\n'
        f'      <path transform="translate(0 2.5)" fillRule="evenodd" clipRule="evenodd" d="{path}" fill={{color}} />\n'
        "      " + text.format(x=60, y=41, fs=40, tl=lock_w - 60, name=name) + "\n"
        "    </svg>\n  );\n}\n",
        icons / "sub-brand/plane-icon.tsx": HEADER + 'import { IconWrapper } from "../icon-wrapper";\nimport type { ISvgIcons } from "../type";\n\n'
        'export function PlaneNewIcon({ color = "currentColor", ...rest }: ISvgIcons) {\n'
        "  return (\n"
        "    <IconWrapper color={color} {...rest}>\n"
        f'      <path transform="translate(1 1) scale(0.2917)" fillRule="evenodd" clipRule="evenodd" d="{path}" fill={{color}} />\n'
        "    </IconWrapper>\n  );\n}\n",
    }
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg width="{lock_w}" height="53" viewBox="0 0 {lock_w} 53" fill="none" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <path transform="translate(0 2.5)" fill-rule="evenodd" d="{path}" fill="#ffffff"/>\n'
        f'  <text x="60" y="41" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-weight="700" '
        f'font-size="40" textLength="{lock_w - 60}" lengthAdjust="spacingAndGlyphs" fill="#ffffff">{name}</text>\n'
        "</svg>\n"
    )
    files[ROOT / "packages/propel/public/plane-lockup-light.svg"] = svg
    files[ROOT / "apps/space/app/assets/plane-logo.svg"] = (
        f'<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <path fill-rule="evenodd" d="{path}" fill="{BRAND["colors"]["primary"]}"/>\n</svg>\n'
    )
    return files


def write_logos(dry_run):
    files = logo_components()
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
        if rel == "docker-compose.yml" and not re.search(r"^name:", new, re.M):
            new = f"name: {slug}\n\n" + new
        elif rel == "docker-compose.yml":
            new = re.sub(r"^name:.*$", f"name: {slug}", new, count=1, flags=re.M)
        if new != text:
            changed += 1
            if not dry_run:
                p.write_text(new, encoding="utf-8", newline="")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="old", help="previously applied brand name to replace")
    ap.add_argument("--from-slug", dest="old_slug", help="previously applied brand slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    old_names = ["Plane"] + ([args.old] if args.old else [])
    old_slugs = ["plane"] + ([args.old_slug] if args.old_slug else [])
    rules = build_rules(old_names)

    print(f"text files changed: {rebrand_text(rules, args.dry_run)}")
    print(f"logo files written: {write_logos(args.dry_run)}")
    print(f"infra files changed: {rebrand_infra(old_slugs, args.dry_run)}")
    if args.dry_run:
        print("dry run: nothing was written")


if __name__ == "__main__":
    main()
