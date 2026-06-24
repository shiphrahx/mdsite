"""Tests for tag collection + rendering."""

from __future__ import annotations

from mdsite.tags import (
    collect_tags,
    normalize_tags,
    render_tag_chips,
    render_tag_index_content,
    render_tag_page_content,
    tag_url,
)


# ---- normalize_tags ----

def test_normalize_list():
    assert normalize_tags(["a", "b"]) == ["a", "b"]


def test_normalize_comma_string():
    assert normalize_tags("a, b ,c") == ["a", "b", "c"]


def test_normalize_dedupes_case_insensitively_keeping_first():
    assert normalize_tags(["Python", "python", "Go"]) == ["Python", "Go"]


def test_normalize_drops_blanks_and_handles_none():
    assert normalize_tags(None) == []
    assert normalize_tags(["", "  ", "x"]) == ["x"]


def test_normalize_scalar():
    assert normalize_tags(42) == ["42"]


# ---- tag_url ----

def test_tag_url_slugifies():
    assert tag_url("/", "Hello World") == "/tags/hello-world/"
    assert tag_url("/docs/", "Go") == "/docs/tags/go/"


# ---- collect_tags ----

def _rec(title, url, tags):
    return {"title": title, "url": url, "meta": {"tags": tags}}


def test_collect_groups_and_sorts():
    records = [
        _rec("B Page", "/b/", ["python", "cli"]),
        _rec("A Page", "/a/", ["python"]),
        _rec("No tags", "/n/", None),
    ]
    tags = collect_tags(records)
    # Tags sorted by slug; pages within a tag sorted by title.
    assert list(tags) == ["cli", "python"]
    assert [p["title"] for p in tags["python"]] == ["A Page", "B Page"]


def test_collect_merges_case_variants_under_first_seen_name():
    records = [_rec("X", "/x/", ["Python"]), _rec("Y", "/y/", ["python"])]
    tags = collect_tags(records)
    assert list(tags) == ["Python"]
    assert len(tags["Python"]) == 2


# ---- rendering ----

def test_render_chips():
    html = render_tag_chips(["python", "go"], "/")
    assert '<a class="tag" href="/tags/python/">python</a>' in html
    assert '<a class="tag" href="/tags/go/">go</a>' in html


def test_render_chips_empty():
    assert render_tag_chips([], "/") == ""


def test_render_chips_escapes():
    html = render_tag_chips(["<x>"], "/")
    assert "&lt;x&gt;" in html


def test_render_tag_index_has_counts():
    content = render_tag_index_content({"python": [{"title": "A", "url": "/a/"}]}, "/")
    assert "<h1>Tags</h1>" in content
    assert 'href="/tags/python/"' in content
    assert '<span class="tag-count">1</span>' in content


def test_render_tag_page_lists_pages():
    content = render_tag_page_content("python", [{"title": "A", "url": "/a/"}])
    assert "Tag: python" in content
    assert '<a href="/a/">A</a>' in content
