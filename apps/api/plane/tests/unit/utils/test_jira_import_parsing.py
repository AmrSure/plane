# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reading, date parsing, markup conversion and analysis of Jira CSV exports."""

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from plane.utils.jira_import.analyzer import analyze, attachment_parts, comment_parts, suggested_group
from plane.utils.jira_import.dates import parse_date, parse_datetime
from plane.utils.jira_import.markup import jira_to_html
from plane.utils.jira_import.reader import JiraCsvError, first, issue_number, read_rows

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "jira"
TZ = ZoneInfo("Asia/Riyadh")


def load(name):
    return (FIXTURES / name).read_bytes()


@pytest.mark.unit
class TestReader:
    def test_repeated_columns_become_lists(self):
        rows = read_rows(load("jira_rich.csv"))
        story = next(r for r in rows if first(r, "Issue key") == "DEMO-2")
        assert story["Labels"] == ["frontend", "ux"]
        assert story["Sprint"] == ["DEMO Sprint 1", "DEMO Sprint 2"]
        assert len(story["Comment"]) == 2
        # Empty repeated cells are dropped
        bug = next(r for r in rows if first(r, "Issue key") == "DEMO-3")
        assert bug["Labels"] == ["backend"]

    def test_bom_is_ignored(self):
        rows = read_rows("﻿Summary,Issue key\nHello,AB-1\n".encode("utf-8"))
        assert first(rows[0], "Summary") == "Hello"

    def test_rejects_files_without_jira_columns(self):
        with pytest.raises(JiraCsvError) as exc:
            read_rows(b"name,value\na,b\n")
        assert str(exc.value) == "missing_columns"

    def test_rejects_empty_file(self):
        with pytest.raises(JiraCsvError):
            read_rows(b"")

    def test_issue_number(self):
        assert issue_number("ALMS-12") == 12
        assert issue_number("nonsense") == 0


@pytest.mark.unit
class TestDates:
    def test_jira_format_in_timezone(self):
        value = parse_datetime("22/Apr/26 2:07 PM", TZ)
        assert (value.year, value.month, value.day, value.hour, value.minute) == (2026, 4, 22, 14, 7)
        assert value.utcoffset().total_seconds() == 3 * 3600

    def test_iso_and_dates(self):
        assert parse_datetime("2026-04-22T10:00:00+00:00", TZ).hour == 10
        assert str(parse_date("19/Apr/26 12:00 AM", TZ)) == "2026-04-19"

    def test_unparseable(self):
        assert parse_datetime("not a date", TZ) is None
        assert parse_datetime("", TZ) is None


@pytest.mark.unit
class TestMarkup:
    def test_formatting(self):
        result = jira_to_html("h2. Goal\nMake it *fast* and _simple_.\n* one\n* two\n[spec|https://example.com/spec]")
        assert "<h2>Goal</h2>" in result
        assert "<strong>fast</strong>" in result
        assert "<em>simple</em>" in result
        assert result.count("<li>") == 2
        assert 'href="https://example.com/spec"' in result

    def test_html_is_never_executed(self):
        result = jira_to_html('<script>alert(1)</script><img src=x onerror="alert(1)">')
        assert "<script" not in result
        assert "<img" not in result
        assert "onerror=" not in result or "&lt;img" in result

    def test_code_block_is_kept_literally(self):
        result = jira_to_html("{code:java}int *a* = 1;{code}")
        assert "<pre><code>" in result
        assert "<strong>" not in result

    def test_empty(self):
        assert jira_to_html("") == "<p></p>"


@pytest.mark.unit
class TestAnalyzer:
    def test_sample_export(self):
        rows = read_rows(load("jira_sample.csv"))
        members = [{"id": "m1", "display_name": "sam", "first_name": "Sam", "last_name": "Rivera", "email": "sam@x.io"}]
        analysis = analyze(rows, members, TZ)

        assert analysis["work_item_count"] == 61
        assert [p["key"] for p in analysis["projects"]] == ["ALMS"]
        groups = {s["name"]: s["suggested_group"] for s in analysis["statuses"]}
        assert groups == {"Done": "completed", "In Progress": "started"}
        assert {p["name"]: p["suggested"] for p in analysis["priorities"]} == {
            "High": "high",
            "Medium": "medium",
            "Highest": "urgent",
        }
        assert [s["name"] for s in analysis["sprints"]] == [f"ALMS Sprint {n}" for n in range(1, 6)]
        # Each inferred sprint starts no earlier than the previous one ended
        for previous, current in zip(analysis["sprints"], analysis["sprints"][1:]):
            assert current["start"] >= previous["end"]
        assert len(analysis["users"]) == 1
        assert analysis["users"][0]["suggested_member_id"] == "m1"
        assert analysis["keys"]["min"] == 2 and analysis["keys"]["max"] == 63
        assert analysis["warnings"] == []

    def test_rich_export(self):
        analysis = analyze(read_rows(load("jira_rich.csv")), [], TZ)
        assert {s["name"]: s["suggested_group"] for s in analysis["statuses"]} == {
            "To Do": "unstarted",
            "In Review": "started",
            "Done": "completed",
            "Won't Do": "cancelled",
        }
        assert [e["key"] for e in analysis["epics"]] == ["DEMO-1"]
        assert analysis["epics"][0]["count"] == 1
        assert analysis["features"]["comments"] and analysis["features"]["story_points"]
        assert analysis["link_columns"] == ["Inward issue link (Blocks)", "Outward issue link (Relates)"]
        assert "unparsed_dates" in analysis["warnings"]
        names = {u["id"]: u["name"] for u in analysis["users"]}
        assert names["aid-1"] == "Alex Admin" and names["aid-9"] == "Pat Unknown"

    def test_parts(self):
        assert comment_parts("01/Mar/26 10:00 AM;aid-1;a; b") == ("01/Mar/26 10:00 AM", "aid-1", "a; b")
        assert attachment_parts("d;u;my;file.png;https://x/y.png") == ("d", "u", "my;file.png", "https://x/y.png")
        assert suggested_group("Backlog", "To Do") == "backlog"
