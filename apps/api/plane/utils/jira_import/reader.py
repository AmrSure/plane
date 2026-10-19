# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reading Jira CSV exports.

Jira repeats a header once per value for multi-valued fields (Labels, Sprint, Comment,
Attachment, Watchers, issue links...). Every row is returned as {header: [values]} with
empty values dropped, so callers use first() for single fields and the list otherwise.
"""

import csv
import io
from typing import Dict, List

REQUIRED_HEADERS = ("Issue key", "Summary")

# Jira exports can hold very large text cells (descriptions, comments)
csv.field_size_limit(16 * 1024 * 1024)


class JiraCsvError(ValueError):
    """The file is not a usable Jira CSV export. The message is a translation-friendly code."""


Row = Dict[str, List[str]]


def decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise JiraCsvError("invalid_encoding")


def read_rows(content: bytes) -> List[Row]:
    text = decode(content)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration:
        raise JiraCsvError("empty_file")
    except csv.Error:
        raise JiraCsvError("invalid_csv")

    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise JiraCsvError("missing_columns")

    rows: List[Row] = []
    try:
        for values in reader:
            if not any(v.strip() for v in values):
                continue
            row: Row = {}
            for header, value in zip(headers, values):
                value = value.strip()
                if value:
                    row.setdefault(header, []).append(value)
            if first(row, "Issue key"):
                rows.append(row)
    except csv.Error:
        raise JiraCsvError("invalid_csv")
    if not rows:
        raise JiraCsvError("no_work_items")
    return rows


def first(row: Row, header: str, default: str = "") -> str:
    values = row.get(header)
    return values[0] if values else default


def all_values(row: Row, *headers: str) -> List[str]:
    out: List[str] = []
    for header in headers:
        out.extend(row.get(header, []))
    return out


def headers_starting_with(row: Row, prefix: str) -> List[str]:
    return [h for h in row if h.startswith(prefix)]


def issue_number(key: str) -> int:
    """ALMS-12 -> 12 (0 when the key has no number)."""
    try:
        return int(key.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def project_key(key: str) -> str:
    return key.rsplit("-", 1)[0] if "-" in key else key
