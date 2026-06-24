"""Atom feed generation for pages carrying a front-matter `date`.

Pages with a parseable `date` become feed entries (newest first). The feed is
written to feed.xml at the output root. Absolute links require `site_url`; when
it is unset we fall back to base-relative URLs (best effort)."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from .search import html_to_text

_SUMMARY_CHARS = 300


def parse_date(value) -> _dt.datetime | None:
    """Coerce a front-matter date into an aware UTC datetime, or None.

    Accepts datetime, date, and ISO-8601 strings ("2024-01-02" or full
    timestamps). Naive values are assumed to be UTC."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        dt = value
    elif isinstance(value, _dt.date):
        dt = _dt.datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        try:
            dt = _dt.datetime.fromisoformat(text)
        except ValueError:
            try:
                d = _dt.date.fromisoformat(text)
            except ValueError:
                return None
            dt = _dt.datetime(d.year, d.month, d.day)
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _rfc3339(dt: _dt.datetime) -> str:
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _xml_escape(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def collect_feed_entries(records: list[dict]) -> list[dict]:
    """Return dated records as feed entries, newest first.

    Each entry: {title, url, date (datetime), summary}. Ties on date keep a
    stable order by title so output is deterministic."""
    entries: list[dict] = []
    for rec in records:
        dt = parse_date(rec.get("meta", {}).get("date"))
        if dt is None:
            continue
        summary = rec.get("meta", {}).get("description")
        if not summary:
            text = html_to_text(rec.get("html", ""))
            summary = text[:_SUMMARY_CHARS]
        entries.append({
            "title": rec["title"], "url": rec["url"],
            "date": dt, "summary": summary,
        })
    entries.sort(key=lambda e: (e["date"], e["title"].lower()), reverse=True)
    return entries


def _abs(site_url: str, url: str) -> str:
    return (site_url + url) if site_url else url


def render_atom(site_title: str, description: str, site_url: str, base: str,
                entries: list[dict], feed_path: str = "feed.xml") -> str:
    """Render an Atom 1.0 feed document."""
    site_url = (site_url or "").rstrip("/")
    home = _abs(site_url, base)
    self_url = _abs(site_url, base + feed_path)
    updated = _rfc3339(entries[0]["date"]) if entries else _rfc3339(
        _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    )
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{_xml_escape(site_title)}</title>",
    ]
    if description:
        lines.append(f"  <subtitle>{_xml_escape(description)}</subtitle>")
    lines += [
        f'  <link href="{_xml_escape(self_url)}" rel="self"/>',
        f'  <link href="{_xml_escape(home)}"/>',
        f"  <id>{_xml_escape(home)}</id>",
        f"  <updated>{updated}</updated>",
    ]
    for e in entries:
        url = _abs(site_url, e["url"])
        lines += [
            "  <entry>",
            f"    <title>{_xml_escape(e['title'])}</title>",
            f'    <link href="{_xml_escape(url)}"/>',
            f"    <id>{_xml_escape(url)}</id>",
            f"    <updated>{_rfc3339(e['date'])}</updated>",
        ]
        if e["summary"]:
            lines.append(f"    <summary>{_xml_escape(e['summary'])}</summary>")
        lines.append("  </entry>")
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def write_feed(out_dir: Path, site_title: str, description: str, site_url: str,
               base: str, entries: list[dict], feed_path: str = "feed.xml") -> None:
    (out_dir / feed_path).write_text(
        render_atom(site_title, description, site_url, base, entries, feed_path),
        encoding="utf-8",
    )
