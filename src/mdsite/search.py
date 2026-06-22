"""Generate search-index.json and sitemap.xml."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Strip tags + collapse whitespace for the search index body text."""
    text = _TAG.sub(" ", html)
    text = unescape(text)
    text = _WS.sub(" ", text).strip()
    return text


def write_search_index(out_dir: Path, records: list[dict], max_chars: int = 2000) -> None:
    """Emit a flat [{title, url, text}] index for client-side search."""
    index = []
    for rec in records:
        text = html_to_text(rec["html"])
        if len(text) > max_chars:
            text = text[:max_chars]
        index.append({"title": rec["title"], "url": rec["url"], "text": text})
    (out_dir / "search-index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )


def write_sitemap(out_dir: Path, urls: list[str], base: str) -> None:
    """Emit a minimal sitemap.xml. URLs are root-relative; no host is
    assumed, so loc values are the site-relative clean URLs."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        lines.append(f"  <url><loc>{_xml_escape(url)}</loc></url>")
    lines.append("</urlset>")
    (out_dir / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )
