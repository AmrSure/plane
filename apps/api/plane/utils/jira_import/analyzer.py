# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Summarise a Jira CSV export so the user can map it before importing."""

import re
from collections import Counter, OrderedDict
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .dates import parse_datetime
from .reader import Row, first, issue_number, project_key

PRIORITY_MAP = {
    "highest": "urgent",
    "blocker": "urgent",
    "critical": "urgent",
    "urgent": "urgent",
    "high": "high",
    "major": "high",
    "medium": "medium",
    "normal": "medium",
    "low": "low",
    "minor": "low",
    "lowest": "low",
    "trivial": "low",
}

CANCELLED_WORDS = ("cancel", "won't", "wont", "declined", "rejected", "duplicate", "invalid", "abandon")
USER_COLUMNS = (
    ("Assignee", "Assignee Id", "assignee"),
    ("Reporter", "Reporter Id", "reporter"),
    ("Creator", "Creator Id", "creator"),
    ("Watchers", "Watchers Id", "watcher"),
)
STORY_POINT_COLUMNS = ("Custom field (Story Points)", "Custom field (Story point estimate)", "Story Points")
EPIC_LINK_COLUMNS = ("Custom field (Epic Link)", "Epic Link", "Parent key")
LINK_PREFIXES = ("Inward issue link (", "Outward issue link (")

SPRINT_FALLBACK_DAYS = 14


def order_sprints(sprints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order sprints by the number in their name ('Sprint 2' < 'Sprint 10'), else by first activity."""

    def number(name: str) -> Optional[int]:
        match = re.search(r"(\d+)\D*$", name or "")
        return int(match.group(1)) if match else None

    if sprints and all(number(s["name"]) is not None for s in sprints):
        return sorted(sprints, key=lambda s: number(s["name"]))
    return sorted(sprints, key=lambda s: (s["start"] is None, s["start"] or 0))


def suggested_priority(name: str) -> str:
    return PRIORITY_MAP.get((name or "").strip().lower(), "none")


def suggested_group(status: str, category: str) -> str:
    name = (status or "").lower()
    cat = (category or "").lower()
    if any(word in name for word in CANCELLED_WORDS):
        return "cancelled"
    if cat == "done" or name in ("done", "closed", "resolved", "complete", "completed"):
        return "completed"
    if cat == "in progress" or any(word in name for word in ("progress", "review", "testing", "qa", "doing")):
        return "started"
    if "backlog" in name:
        return "backlog"
    return "unstarted"


def is_epic(row: Row) -> bool:
    return first(row, "Issue Type").strip().lower() == "epic"


def comment_parts(value: str) -> Tuple[str, str, str]:
    """'date;accountId;body' -> (date, account id, body). Bodies may contain ';'."""
    parts = value.split(";", 2)
    if len(parts) == 3 and parts[0] and any(ch.isdigit() for ch in parts[0]):
        return parts[0].strip(), parts[1].strip(), parts[2]
    return "", "", value


def attachment_parts(value: str) -> Tuple[str, str, str, str]:
    """'date;accountId;file name;url' -> parts. Falls back to treating the value as a url."""
    parts = value.split(";")
    if len(parts) >= 4:
        return parts[0].strip(), parts[1].strip(), ";".join(parts[2:-1]).strip(), parts[-1].strip()
    return "", "", value.rsplit("/", 1)[-1], value


def link_columns(rows: Iterable[Row]) -> List[str]:
    headers = set()
    for row in rows:
        headers.update(h for h in row if h.startswith(LINK_PREFIXES))
    return sorted(headers)


def collect_users(rows: List[Row]) -> "OrderedDict[str, Dict[str, Any]]":
    users: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def add(account_id: str, name: str, role: str):
        key = account_id or f"name:{name.strip().lower()}"
        if not key or key == "name:":
            return
        user = users.setdefault(key, {"id": key, "name": name or account_id, "roles": [], "count": 0})
        if name and (not user["name"] or user["name"] == account_id):
            user["name"] = name
        if role not in user["roles"]:
            user["roles"].append(role)
        user["count"] += 1

    for row in rows:
        for name_col, id_col, role in USER_COLUMNS:
            names, ids = row.get(name_col, []), row.get(id_col, [])
            for index in range(max(len(names), len(ids))):
                add(ids[index] if index < len(ids) else "", names[index] if index < len(names) else "", role)
        for comment in row.get("Comment", []):
            _, account_id, _ = comment_parts(comment)
            if account_id:
                add(account_id, "", "commenter")
    return users


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def suggest_members(users: Dict[str, Dict[str, Any]], members: List[Dict[str, Any]]) -> None:
    """Attach suggested_member_id by matching names (display name, full name, email local part)."""
    index: Dict[str, str] = {}
    for member in members:
        candidates = [
            member.get("display_name"),
            f"{member.get('first_name', '')} {member.get('last_name', '')}",
            (member.get("email") or "").split("@")[0],
        ]
        for candidate in candidates:
            key = _normalize(candidate)
            if key and key not in index:
                index[key] = str(member["id"])
    for user in users.values():
        user["suggested_member_id"] = index.get(_normalize(user["name"]))


def analyze(rows: List[Row], members: List[Dict[str, Any]], tz: ZoneInfo) -> Dict[str, Any]:
    projects: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    statuses: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    priorities: Counter = Counter()
    issue_types: Counter = Counter()
    labels: Counter = Counter()
    sprints: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    epics: List[Dict[str, Any]] = []
    key_counts: Counter = Counter()
    date_errors = 0
    features = {
        "comments": False,
        "attachments": False,
        "links": False,
        "story_points": False,
        "parents": False,
        "watchers": False,
        "due_dates": False,
        "start_dates": False,
        "descriptions": False,
    }

    for row in rows:
        key = first(row, "Issue key")
        key_counts[key] += 1
        pkey = first(row, "Project key") or project_key(key)
        project = projects.setdefault(pkey, {"key": pkey, "name": first(row, "Project name") or pkey, "count": 0})
        project["count"] += 1

        status, category = first(row, "Status"), first(row, "Status Category")
        if status:
            entry = statuses.setdefault(
                status,
                {
                    "name": status,
                    "category": category,
                    "count": 0,
                    "suggested_group": suggested_group(status, category),
                },
            )
            entry["count"] += 1

        priorities[first(row, "Priority") or "None"] += 1
        issue_type = first(row, "Issue Type")
        if issue_type:
            issue_types[issue_type] += 1
        for label in row.get("Labels", []):
            labels[label] += 1

        created = parse_datetime(first(row, "Created"), tz)
        finished = parse_datetime(first(row, "Resolved"), tz) or parse_datetime(first(row, "Updated"), tz)
        for column in ("Created", "Updated", "Resolved", "Due date", "Custom field (Start date)"):
            if first(row, column) and not parse_datetime(first(row, column), tz):
                date_errors += 1

        for sprint_name in row.get("Sprint", []):
            sprint = sprints.setdefault(sprint_name, {"name": sprint_name, "count": 0, "start": None, "end": None})
            sprint["count"] += 1
            if created and (sprint["start"] is None or created < sprint["start"]):
                sprint["start"] = created
            if finished and (sprint["end"] is None or finished > sprint["end"]):
                sprint["end"] = finished

        if is_epic(row):
            epics.append({"key": key, "id": first(row, "Issue id"), "summary": first(row, "Summary"), "count": 0})

        features["comments"] |= bool(row.get("Comment"))
        features["attachments"] |= bool(row.get("Attachment"))
        features["links"] |= any(h.startswith(LINK_PREFIXES) for h in row)
        features["story_points"] |= any(first(row, c) for c in STORY_POINT_COLUMNS)
        features["parents"] |= bool(
            first(row, "Parent") or first(row, "Parent id") or any(first(row, c) for c in EPIC_LINK_COLUMNS)
        )
        features["watchers"] |= bool(row.get("Watchers"))
        features["due_dates"] |= bool(first(row, "Due date"))
        features["start_dates"] |= bool(first(row, "Custom field (Start date)"))
        features["descriptions"] |= bool(first(row, "Description"))

    # Children per epic (by parent id or epic link key)
    epic_by_id = {e["id"]: e for e in epics if e["id"]}
    epic_by_key = {e["key"]: e for e in epics}
    for row in rows:
        parent = first(row, "Parent") or first(row, "Parent id")
        epic = epic_by_id.get(parent) or next(
            (epic_by_key.get(first(row, c)) for c in EPIC_LINK_COLUMNS if first(row, c)), None
        )
        if epic:
            epic["count"] += 1

    users = collect_users(rows)
    suggest_members(users, members)

    numbers = [issue_number(k) for k in key_counts]
    warnings = []
    if len(projects) > 1:
        warnings.append("multiple_projects")
    if any(count > 1 for count in key_counts.values()):
        warnings.append("duplicate_keys")
    if date_errors:
        warnings.append("unparsed_dates")

    def iso(value):
        return value.isoformat() if value else None

    sprint_list = []
    previous_end = None
    for sprint in order_sprints(list(sprints.values())):
        start, end = sprint["start"], sprint["end"]
        # Items are often created long before their sprint; a sprint starts no earlier than the previous one ended
        if start and previous_end and previous_end > start:
            start = previous_end
        if start and (not end or end < start):
            end = start + timedelta(days=SPRINT_FALLBACK_DAYS)
        previous_end = end or previous_end
        sprint_list.append({**sprint, "start": iso(start), "end": iso(end)})

    return {
        "work_item_count": len(rows),
        "projects": list(projects.values()),
        "statuses": list(statuses.values()),
        "priorities": [
            {"name": name, "count": count, "suggested": suggested_priority(name)}
            for name, count in priorities.most_common()
        ],
        "issue_types": [{"name": name, "count": count} for name, count in issue_types.most_common()],
        "labels": [{"name": name, "count": count} for name, count in labels.most_common()],
        "sprints": sprint_list,
        "epics": epics,
        "users": list(users.values()),
        "link_columns": link_columns(rows),
        "features": features,
        "keys": {
            "min": min(numbers) if numbers else 0,
            "max": max(numbers) if numbers else 0,
            "duplicates": sorted(k for k, c in key_counts.items() if c > 1)[:50],
        },
        "date_errors": date_errors,
        "warnings": warnings,
    }
