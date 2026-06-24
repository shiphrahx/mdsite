"""Tag collection + tag-page/chip rendering.

Pages declare tags via front matter (`tags: [a, b]` or a single string). We
build an index of tag -> pages, render small tag "chips" under each tagged
page, and emit `/tags/` and `/tags/<slug>/` listing pages."""

from __future__ import annotations

from html import escape

from .render import slugify


def normalize_tags(value) -> list[str]:
    """Coerce a front-matter `tags` value into a clean list of strings.

    Accepts a list, a comma-separated string, or a single scalar. Blank
    entries are dropped; order is preserved with duplicates removed."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        items = [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        tag = str(item).strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def tag_url(base: str, tag: str) -> str:
    return f"{base}tags/{slugify(tag)}/"


def collect_tags(records: list[dict]) -> dict[str, list[dict]]:
    """Map tag -> list of {title, url} for pages carrying that tag.

    Tags are grouped case-insensitively by their first-seen display form; the
    page lists are sorted by title and the mapping is sorted by tag name."""
    by_slug: dict[str, dict] = {}
    for rec in records:
        tags = normalize_tags(rec.get("meta", {}).get("tags"))
        for tag in tags:
            slug = slugify(tag)
            entry = by_slug.setdefault(slug, {"name": tag, "pages": []})
            entry["pages"].append({"title": rec["title"], "url": rec["url"]})
    result: dict[str, list[dict]] = {}
    for slug in sorted(by_slug):
        entry = by_slug[slug]
        pages = sorted(entry["pages"], key=lambda p: p["title"].lower())
        result[entry["name"]] = pages
    return result


def render_tag_chips(tags: list[str], base: str) -> str:
    """Render a page's tags as a row of links to their tag pages."""
    if not tags:
        return ""
    chips = "".join(
        f'<a class="tag" href="{escape(tag_url(base, t), quote=True)}">'
        f'{escape(t)}</a>'
        for t in tags
    )
    return f'<div class="page-tags">{chips}</div>'


def render_tag_index_content(tags: dict[str, list[dict]], base: str) -> str:
    """HTML body for the /tags/ overview page."""
    items = "".join(
        f'<li><a href="{escape(tag_url(base, name), quote=True)}">{escape(name)}</a>'
        f' <span class="tag-count">{len(pages)}</span></li>'
        for name, pages in tags.items()
    )
    return f'<h1>Tags</h1>\n<ul class="tag-list">{items}</ul>'


def render_tag_page_content(name: str, pages: list[dict]) -> str:
    """HTML body for a single /tags/<slug>/ page."""
    items = "".join(
        f'<li><a href="{escape(p["url"], quote=True)}">{escape(p["title"])}</a></li>'
        for p in pages
    )
    return f'<h1>Tag: {escape(name)}</h1>\n<ul class="tag-list">{items}</ul>'
