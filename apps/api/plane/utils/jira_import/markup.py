# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Convert Jira wiki markup to safe HTML.

The input is escaped first, so any HTML in a Jira field is shown as text; the result is
then passed through the editor's nh3 sanitizer.
"""

import html
import re
from typing import List

from plane.utils.content_validator import validate_html_content

_LINK = re.compile(r"\[([^\]|\n]+)\|(https?://[^\]\s]+)\]")
_BARE_LINK = re.compile(r"\[(https?://[^\]\s]+)\]")
_BOLD = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_ITALIC = re.compile(r"(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])")
_STRIKE = re.compile(r"(?<![\w-])-(?!\s)([^-\n]+?)(?<!\s)-(?![\w-])")
_MONO = re.compile(r"\{\{(.+?)\}\}")
_HEADING = re.compile(r"^h([1-6])\.\s+(.*)$")
_LIST = re.compile(r"^([*#]+)\s+(.*)$")
_COLOR = re.compile(r"\{color(?::[^}]*)?\}")
_BLOCK = re.compile(r"\{(code|noformat)(?::[^}]*)?\}(.*?)\{\1\}", re.S)
_QUOTE = re.compile(r"\{quote\}(.*?)\{quote\}", re.S)


def _inline(text: str) -> str:
    text = _COLOR.sub("", text)
    text = _MONO.sub(r"<code>\1</code>", text)
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    text = _BARE_LINK.sub(r'<a href="\1">\1</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    text = _STRIKE.sub(r"<s>\1</s>", text)
    return text


def _table_row(line: str) -> str:
    header = line.startswith("||")
    cells = [c.strip() for c in re.split(r"\|\|?", line.strip("|").strip()) if c is not None]
    tag = "th" if header else "td"
    return "<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>"


def jira_to_html(text: str) -> str:
    if not text or not text.strip():
        return "<p></p>"

    escaped = html.escape(text.replace("\r\n", "\n").replace("\r", "\n"), quote=False)

    # Protect code/noformat and quote blocks from inline processing
    blocks: List[str] = []

    def stash(fragment: str) -> str:
        blocks.append(fragment)
        return f"\x00{len(blocks) - 1}\x00"

    escaped = _BLOCK.sub(lambda m: stash(f"<pre><code>{m.group(2).strip(chr(10))}</code></pre>"), escaped)
    escaped = _QUOTE.sub(lambda m: stash(f"<blockquote><p>{_inline(m.group(1).strip())}</p></blockquote>"), escaped)

    out: List[str] = []
    paragraph: List[str] = []
    list_stack: List[str] = []
    table: List[str] = []

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def close_lists(depth: int = 0):
        while len(list_stack) > depth:
            out.append(f"</li></{list_stack.pop()}>")

    def flush_table():
        if table:
            out.append("<table><tbody>" + "".join(table) + "</tbody></table>")
            table.clear()

    for raw in escaped.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("\x00") and stripped.endswith("\x00"):
            flush_paragraph(), close_lists(), flush_table()
            out.append(blocks[int(stripped.strip("\x00"))])
            continue
        if not stripped:
            flush_paragraph(), close_lists(), flush_table()
            continue
        heading = _HEADING.match(stripped)
        if heading:
            flush_paragraph(), close_lists(), flush_table()
            level = heading.group(1)
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        if stripped.startswith("|"):
            flush_paragraph(), close_lists()
            table.append(_table_row(stripped))
            continue
        flush_table()
        item = _LIST.match(stripped)
        if item:
            flush_paragraph()
            markers, content = item.group(1), item.group(2)
            depth = len(markers)
            kind = "ol" if markers[-1] == "#" else "ul"
            close_lists(depth)
            if len(list_stack) == depth:
                if list_stack[-1] == kind:
                    out.append("</li><li>")
                else:
                    close_lists(depth - 1)
            while len(list_stack) < depth:
                list_stack.append(kind)
                out.append(f"<{kind}><li>")
            out.append(f"<p>{_inline(content)}</p>")
            continue
        close_lists()
        paragraph.append(line)

    flush_paragraph(), close_lists(), flush_table()
    result = "".join(out).replace("\x00", "")
    is_valid, _, clean = validate_html_content(result)
    if not is_valid:
        return "<p>" + html.escape(text) + "</p>"
    return clean or result


def plain_paragraph(text: str) -> str:
    return f"<p>{html.escape(text)}</p>"
