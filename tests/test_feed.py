"""Tests for Atom feed generation."""

from __future__ import annotations

import datetime as dt

from mdsite.feed import collect_feed_entries, parse_date, render_atom


# ---- parse_date ----

def test_parse_date_string():
    assert parse_date("2024-01-02") == dt.datetime(2024, 1, 2, tzinfo=dt.timezone.utc)


def test_parse_datetime_object():
    d = dt.datetime(2024, 5, 6, 12, 0)
    assert parse_date(d).hour == 12


def test_parse_date_object():
    assert parse_date(dt.date(2024, 3, 4)) == dt.datetime(2024, 3, 4, tzinfo=dt.timezone.utc)


def test_parse_iso_timestamp_with_tz():
    out = parse_date("2024-01-02T08:00:00+00:00")
    assert out == dt.datetime(2024, 1, 2, 8, tzinfo=dt.timezone.utc)


def test_parse_invalid_returns_none():
    assert parse_date("not a date") is None
    assert parse_date(None) is None
    assert parse_date(123) is None


# ---- collect_feed_entries ----

def _rec(title, url, date, **meta):
    m = {"date": date, **meta}
    return {"title": title, "url": url, "html": "<p>body text</p>", "meta": m}


def test_collect_sorts_newest_first_and_skips_undated():
    records = [
        _rec("Old", "/o/", "2020-01-01"),
        _rec("New", "/n/", "2024-01-01"),
        {"title": "Undated", "url": "/u/", "html": "<p>x</p>", "meta": {}},
    ]
    entries = collect_feed_entries(records)
    assert [e["title"] for e in entries] == ["New", "Old"]


def test_collect_summary_prefers_description_then_excerpt():
    records = [
        _rec("A", "/a/", "2024-01-01", description="Custom summary"),
        _rec("B", "/b/", "2023-01-01"),
    ]
    entries = collect_feed_entries(records)
    by_title = {e["title"]: e for e in entries}
    assert by_title["A"]["summary"] == "Custom summary"
    assert "body text" in by_title["B"]["summary"]


# ---- render_atom ----

def test_render_atom_absolute_urls_with_site_url():
    entries = collect_feed_entries([_rec("Post", "/post/", "2024-01-02")])
    xml = render_atom("My Site", "desc", "https://example.com", "/", entries)
    assert xml.startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert "<feed xmlns=\"http://www.w3.org/2005/Atom\">" in xml
    assert "<title>My Site</title>" in xml
    assert "<subtitle>desc</subtitle>" in xml
    assert '<link href="https://example.com/feed.xml" rel="self"/>' in xml
    assert "<link href=\"https://example.com/post/\"/>" in xml
    assert "<updated>2024-01-02T00:00:00Z</updated>" in xml


def test_render_atom_relative_without_site_url():
    entries = collect_feed_entries([_rec("Post", "/post/", "2024-01-02")])
    xml = render_atom("Site", "", "", "/", entries)
    assert '<link href="/post/"/>' in xml
    # No subtitle line when description is empty.
    assert "<subtitle>" not in xml


def test_render_atom_escapes():
    entries = collect_feed_entries([_rec("A & B", "/a/", "2024-01-02")])
    xml = render_atom("S&Co", "", "", "/", entries)
    assert "A &amp; B" in xml
    assert "S&amp;Co" in xml
