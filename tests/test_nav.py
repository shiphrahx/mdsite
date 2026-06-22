"""Tests for nav tree construction + prev/next ordering."""

from __future__ import annotations

from mdsite.nav import (
    Link,
    Page,
    build_nav,
    is_index_file,
    prev_next_map,
)


def _p(rel, url, title, order=None, is_index=False):
    return Page(rel=rel, url=url, title=title, order=order, is_index=is_index)


# ---- is_index_file ----

def test_is_index_file():
    assert is_index_file("index.md")
    assert is_index_file("README.md")
    assert is_index_file("foo/index.markdown")
    assert is_index_file("foo/README.md")
    assert not is_index_file("foo.md")
    assert not is_index_file("foo/bar.md")


def test_is_index_file_backslash_normalized():
    assert is_index_file("foo\\index.md")


# ---- build_nav: structure ----

def test_root_index_becomes_root_url():
    pages = [_p("index.md", "/", "Home", 1, True)]
    tree, ordered = build_nav(pages)
    assert tree.url == "/"
    assert ordered[0].url == "/"


def test_nested_folder_tree():
    pages = [
        _p("index.md", "/", "Home", 1, True),
        _p("guide/index.md", "/guide/", "Guide", None, True),
        _p("guide/intro.md", "/guide/intro/", "Intro"),
        _p("guide/deep/x.md", "/guide/deep/x/", "X"),
    ]
    tree, _ = build_nav(pages)
    names = [c.name for c in tree.children]
    assert names == ["guide"]
    guide = tree.children[0]
    assert guide.url == "/guide/"
    assert guide.title == "Guide"
    assert [pg.url for pg in guide.pages] == ["/guide/intro/"]
    assert [c.name for c in guide.children] == ["deep"]


def test_folder_without_index_has_no_url():
    pages = [
        _p("index.md", "/", "Home", 1, True),
        _p("sec/a.md", "/sec/a/", "A"),
    ]
    tree, _ = build_nav(pages)
    sec = tree.children[0]
    assert sec.name == "sec"
    assert sec.url is None
    # Falls back to the segment name as title.
    assert sec.title == "sec"


# ---- build_nav: ordering ----

def test_pages_sorted_order_then_title():
    pages = [
        _p("index.md", "/", "Home", 1, True),
        _p("z.md", "/z/", "Zed", None),
        _p("a.md", "/a/", "Alpha", None),
        _p("first.md", "/first/", "First", 1),
        _p("second.md", "/second/", "Second", 2),
    ]
    _, ordered = build_nav(pages)
    urls = [l.url for l in ordered]
    # Root index first, then ordered pages (1,2), then alphabetical None pages.
    assert urls == ["/", "/first/", "/second/", "/a/", "/z/"]


def test_children_sorted_by_name():
    pages = [
        _p("index.md", "/", "Home", 1, True),
        _p("zeta/a.md", "/zeta/a/", "A"),
        _p("alpha/a.md", "/alpha/a/", "A"),
    ]
    tree, _ = build_nav(pages)
    assert [c.name for c in tree.children] == ["alpha", "zeta"]


# ---- prev_next_map ----

def test_prev_next_map():
    ordered = [Link("/", "Home"), Link("/a/", "A"), Link("/b/", "B")]
    nm = prev_next_map(ordered)
    assert nm["/"]["prev"] is None
    assert nm["/"]["next"].url == "/a/"
    assert nm["/a/"]["prev"].url == "/"
    assert nm["/a/"]["next"].url == "/b/"
    assert nm["/b/"]["next"] is None


def test_prev_next_single():
    nm = prev_next_map([Link("/", "Home")])
    assert nm["/"]["prev"] is None
    assert nm["/"]["next"] is None
