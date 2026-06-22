"""Build the nav tree + prev/next ordering from page records."""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass
class Page:
    rel: str          # source-relative path, forward-slash normalized
    url: str          # clean output URL
    title: str
    order: int | None
    is_index: bool


@dataclass
class NavNode:
    name: str
    url: str | None = None
    title: str | None = None
    children: list["NavNode"] = field(default_factory=list)
    pages: list[Page] = field(default_factory=list)


@dataclass
class Link:
    url: str
    title: str


def _page_sort_key(p: Page):
    # order-present pages first (by order), then by title; mirrors Node.
    has_order = 0 if p.order is not None else 1
    return (has_order, p.order if p.order is not None else 0, p.title.lower())


def _cmp_pages(a: Page, b: Page) -> int:
    ka, kb = _page_sort_key(a), _page_sort_key(b)
    return -1 if ka < kb else (1 if ka > kb else 0)


def build_nav(pages: list[Page]):
    """Return (tree, ordered). tree is the root NavNode; ordered is a flat
    list of Link in nav order for prev/next."""
    # Mutable build phase uses dict children keyed by segment name.
    root_children: dict = {}
    root = {"name": "", "url": None, "title": None, "children": root_children, "pages": []}

    for page in pages:
        segments = page.rel.split("/")
        dir_segments = segments[:-1]
        node = root
        for seg in dir_segments:
            if seg not in node["children"]:
                node["children"][seg] = {
                    "name": seg, "url": None, "title": seg,
                    "children": {}, "pages": [],
                }
            node = node["children"][seg]
        if page.is_index:
            node["url"] = page.url
            node["title"] = page.title
        else:
            node["pages"].append(page)

    def finalize(node) -> NavNode:
        children = sorted(
            (finalize(c) for c in node["children"].values()),
            key=lambda c: c.name.lower(),
        )
        pages = sorted(node["pages"], key=functools.cmp_to_key(_cmp_pages))
        return NavNode(
            name=node["name"], url=node["url"], title=node["title"],
            children=children, pages=pages,
        )

    tree = finalize(root)

    ordered: list[Link] = []

    def flatten(node: NavNode) -> None:
        if node.url:
            ordered.append(Link(url=node.url, title=node.title or ""))
        for page in node.pages:
            ordered.append(Link(url=page.url, title=page.title))
        for child in node.children:
            flatten(child)

    flatten(tree)
    return tree, ordered


def prev_next_map(ordered: list[Link]) -> dict:
    """Map url -> {'prev': Link|None, 'next': Link|None}."""
    result: dict = {}
    for i, link in enumerate(ordered):
        result[link.url] = {
            "prev": ordered[i - 1] if i > 0 else None,
            "next": ordered[i + 1] if i < len(ordered) - 1 else None,
        }
    return result


def is_index_file(rel: str) -> bool:
    base = PurePosixPath(rel.replace("\\", "/")).stem.lower()
    return base in ("index", "readme")
