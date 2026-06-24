"""Tests for search-index + sitemap generation."""

from __future__ import annotations

import json

from mdsite.render import Heading
from mdsite.search import html_to_text, write_search_index, write_sitemap


# ---- html_to_text ----

def test_strips_tags():
    assert html_to_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_unescapes_entities():
    assert html_to_text("a &amp; b &lt;c&gt;") == "a & b <c>"


def test_collapses_whitespace():
    assert html_to_text("a\n\n  b\t c") == "a b c"


def test_empty_html():
    assert html_to_text("") == ""
    assert html_to_text("<br><hr>") == ""


# ---- write_search_index ----

def test_index_shape(tmp_path):
    records = [
        {"title": "Home", "url": "/", "html": "<p>Hello world</p>", "headings": []},
        {"title": "Page", "url": "/p/", "html": "<h2>Sec</h2>", "headings": []},
    ]
    write_search_index(tmp_path, records)
    data = json.loads((tmp_path / "search-index.json").read_text(encoding="utf-8"))
    assert [r["url"] for r in data] == ["/", "/p/"]
    assert all(set(r) == {"title", "url", "text", "headings"} for r in data)
    assert data[0]["text"] == "Hello world"


def test_index_includes_h2_h3_headings(tmp_path):
    records = [{
        "title": "Page", "url": "/p/", "html": "<p>body</p>",
        "headings": [
            Heading(1, "Title", "title"),
            Heading(2, "Install", "install"),
            Heading(3, "Steps", "steps"),
            Heading(4, "Detail", "detail"),
        ],
    }]
    write_search_index(tmp_path, records)
    data = json.loads((tmp_path / "search-index.json").read_text(encoding="utf-8"))
    # Only H2/H3 are indexed for ranking; H1 (page title) and H4+ excluded.
    assert data[0]["headings"] == ["Install", "Steps"]


def test_index_truncated_to_max_chars(tmp_path):
    long = "<p>" + ("x " * 5000) + "</p>"
    records = [{"title": "T", "url": "/", "html": long, "headings": []}]
    write_search_index(tmp_path, records, max_chars=100)
    data = json.loads((tmp_path / "search-index.json").read_text(encoding="utf-8"))
    assert len(data[0]["text"]) <= 100


def test_index_unicode_preserved(tmp_path):
    records = [{"title": "Café", "url": "/c/", "html": "<p>Crème brûlée</p>", "headings": []}]
    write_search_index(tmp_path, records)
    raw = (tmp_path / "search-index.json").read_text(encoding="utf-8")
    assert "Crème brûlée" in raw  # ensure_ascii=False


# ---- write_sitemap ----

def test_sitemap_structure(tmp_path):
    write_sitemap(tmp_path, ["/", "/a/", "/b/"], "/")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<urlset" in xml
    assert xml.count("<url>") == 3
    assert "<loc>/a/</loc>" in xml


def test_sitemap_escapes_special_chars(tmp_path):
    write_sitemap(tmp_path, ["/a?x=1&y=2/"], "/")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "&amp;" in xml
    assert "&y=2" not in xml.replace("&amp;", "")


def test_sitemap_empty(tmp_path):
    write_sitemap(tmp_path, [], "/")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "<urlset" in xml
    assert "<url>" not in xml
