# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Parsing the date formats found in Jira CSV exports."""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

FORMATS = (
    "%d/%b/%y %I:%M %p",  # 22/Apr/26 2:07 PM (Jira default)
    "%d/%b/%Y %I:%M %p",
    "%d/%b/%y %H:%M",
    "%d/%b/%Y %H:%M",
    "%d/%b/%y",
    "%d/%b/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y",
)


def parse_datetime(value: Optional[str], tz: ZoneInfo) -> Optional[datetime]:
    """Parse a Jira date string as an aware datetime in tz. Returns None when unparseable."""
    if not value:
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)
    except ValueError:
        pass
    for fmt in FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def parse_date(value: Optional[str], tz: ZoneInfo) -> Optional[date]:
    parsed = parse_datetime(value, tz)
    return parsed.date() if parsed else None


def safe_zone(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")
