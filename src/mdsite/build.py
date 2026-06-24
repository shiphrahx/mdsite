"""Walk the source tree, render Markdown, write the static site."""

from __future__ import annotations

import shutil
from html import escape
from pathlib import Path, PurePosixPath

import frontmatter

from .config import load_config, make_exclude_matcher
from .lastmod import last_updated
from .nav import Page, build_nav, is_index_file, prev_next_map
from .render import first_h1, render, slugify
from .layout import (
    render_nav, render_page, render_prev_next, render_toc, write_assets,
)
from .search import write_search_index, write_sitemap

MD_EXT = {".md", ".markdown"}


def _walk(root: Path) -> list[str]:
    """Return source-relative forward-slash paths of all files under root."""
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def copy_to_assets(src: Path, out: Path, rel: str, base: str) -> str | None:
    """Copy a source-relative file into out/assets/, returning its base-relative
    URL (e.g. '/assets/logo.svg'), or None if the source file is missing."""
    source = src / rel
    name = PurePosixPath(rel).name
    try:
        data = source.read_bytes()
    except OSError:
        return None
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / name).write_bytes(data)
    return f"{base}assets/{name}"


def output_path_for(rel: str) -> str:
    """Map a source .md path to its output html path (forward-slash).
    foo/bar.md   -> foo/bar/index.html
    foo/index.md -> foo/index.html
    index.md     -> index.html
    """
    rp = PurePosixPath(rel)
    base = rp.stem.lower()
    parent = rp.parent
    if base in ("index", "readme"):
        return (parent / "index.html").as_posix()
    return (parent / slugify(rp.stem) / "index.html").as_posix()


def url_for(out_path: str, base: str) -> str:
    """Convert an output html path to a clean URL ('/foo/bar/')."""
    url = out_path[: -len("index.html")] if out_path.endswith("index.html") else out_path
    if not url.startswith("/"):
        url = "/" + url
    prefix = base.rstrip("/")
    joined = (prefix + url) or "/"
    while "//" in joined:
        joined = joined.replace("//", "/")
    return joined or "/"


def _make_link_rewrite(rel: str, url_map: dict, broken: list | None = None):
    """Per-file rewriter: resolve a relative .md href to its clean URL.

    A relative .md/.markdown target that is not in url_map (a typo, or a link
    to an excluded/draft page that will 404) is recorded in `broken` as
    (source_rel, original_href) when a collector list is supplied."""
    from_dir = PurePosixPath(rel).parent

    def rewrite(href: str) -> str:
        if "://" in href or href.startswith("#") or href.startswith("mailto:"):
            return href
        path_part, _, frag = href.partition("#")
        path_part, _, query = path_part.partition("?")
        if not path_part.lower().endswith((".md", ".markdown")):
            return href
        target = (from_dir / path_part).as_posix()
        # Normalize ../ and ./ segments.
        target = PurePosixPath(target)
        parts: list[str] = []
        for seg in target.parts:
            if seg == "..":
                if parts:
                    parts.pop()
            elif seg not in (".", ""):
                parts.append(seg)
        norm = "/".join(parts)
        url = url_map.get(norm)
        if not url:
            if broken is not None:
                broken.append((rel, href))
            return href
        if query:
            url = f"{url}?{query}"
        return f"{url}#{frag}" if frag else url

    return rewrite


def build(src_dir: str, opts: dict | None = None, live_reload: str = "") -> dict:
    opts = opts or {}
    src = Path(src_dir).resolve()
    out = Path(opts.get("out", "./dist")).resolve()
    # Normalize base so template concatenation ("{base}assets/...") and clean
    # URLs always agree: leading + trailing slash. Accepts "docs", "/docs",
    # "/docs/" -> "/docs/".
    base = opts.get("base", "/") or "/"
    if not base.startswith("/"):
        base = "/" + base
    if not base.endswith("/"):
        base = base + "/"

    if not src.exists():
        raise RuntimeError(f"source folder not found: {src_dir}")
    if not src.is_dir():
        raise RuntimeError(f"source is not a directory: {src_dir}")

    config = load_config(src)
    is_excluded = make_exclude_matcher(config.get("exclude", []))
    site_title = opts.get("title") or config.get("title") or src.name

    all_files = [f for f in _walk(src) if not is_excluded(f)]
    md_files = [f for f in all_files if PurePosixPath(f).suffix.lower() in MD_EXT]
    assets = [f for f in all_files if PurePosixPath(f).suffix.lower() not in MD_EXT]

    # README.md acts as the folder index only when no index.md exists.
    # Drop README.md siblings of an index.md so they don't collide.
    dirs_with_index: set[str] = set()
    for rel in md_files:
        rp = PurePosixPath(rel)
        if rp.stem.lower() == "index":
            dirs_with_index.add(rp.parent.as_posix())
    kept: list[str] = []
    for rel in md_files:
        rp = PurePosixPath(rel)
        if rp.stem.lower() == "readme" and rp.parent.as_posix() in dirs_with_index:
            print(f"warn: {rel} ignored — index file present in same folder")
            continue
        kept.append(rel)
    md_files = kept

    if not md_files:
        raise RuntimeError(f"no .md files found in {src_dir}")

    if opts.get("clean"):
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    # Pre-pass: read + parse front matter, dropping drafts and undecodable
    # files. Done before building url_map so links to drafts are NOT rewritten
    # to clean URLs that will never exist (the draft is excluded from output).
    parsed: list[dict] = []
    for rel in md_files:
        abs_path = src / rel
        try:
            raw = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"warn: non-UTF-8 file with .md extension {rel} — skipping")
            continue

        data: dict = {}
        content = raw
        try:
            post = frontmatter.loads(raw)
            data = post.metadata
            content = post.content
        except Exception as err:  # noqa: BLE001
            print(f"warn: malformed front matter in {rel} — ignoring ({err})")

        if data.get("draft") is True:
            continue

        parsed.append({"rel": rel, "data": data, "content": content})

    # URL map covers only files that will actually be emitted.
    url_map: dict[str, str] = {
        p["rel"]: url_for(output_path_for(p["rel"]), base) for p in parsed
    }

    # Pass 1: render -> page records.
    pages: list[Page] = []
    records: list[dict] = []
    seen_outputs: dict[str, str] = {}
    broken_links: list[tuple[str, str]] = []
    for entry in parsed:
        rel, data, content = entry["rel"], entry["data"], entry["content"]

        rendered = render(
            content, link_rewrite=_make_link_rewrite(rel, url_map, broken_links)
        )
        title = data.get("title") or first_h1(rendered.headings) or PurePosixPath(rel).stem

        out_rel = output_path_for(rel)
        if out_rel in seen_outputs:
            print(f"warn: duplicate output path {out_rel} "
                  f"(from {seen_outputs[out_rel]} and {rel}) — last wins")
        seen_outputs[out_rel] = rel

        order = data.get("order")
        order = order if isinstance(order, int) else None

        pages.append(Page(
            rel=rel, url=url_map[rel], title=title,
            order=order, is_index=is_index_file(rel),
        ))
        records.append({
            "rel": rel,
            "out_rel": out_rel, "title": title,
            "html": rendered.html, "headings": rendered.headings,
            "url": url_map[rel],
        })

    tree, ordered = build_nav(pages)
    neighbors = prev_next_map(ordered)

    theme = config.get("theme", "auto")
    footer = config.get("footer", "")
    description = config.get("description", "")

    # Nav tree is identical on every page (current page highlighted client-
    # side), so render it once instead of per page.
    nav_html = render_nav(tree, base)

    # Site-wide head/header extras (favicon + logo), identical on every page.
    head_extra_parts: list[str] = []
    favicon = config.get("favicon")
    if favicon:
        url = copy_to_assets(src, out, favicon, base)
        if url:
            head_extra_parts.append(f'<link rel="icon" href="{escape(url, quote=True)}">')
        else:
            print(f"warn: favicon file not found: {favicon} — skipping")
    logo_html = ""
    logo = config.get("logo")
    if logo:
        url = copy_to_assets(src, out, logo, base)
        if url:
            logo_html = f'<img class="site-logo" src="{escape(url, quote=True)}" alt="">'
        else:
            print(f"warn: logo file not found: {logo} — skipping")
    head_extra = "".join(head_extra_parts)

    last_updated_mode = config.get("last_updated")

    # Pass 2: assemble + write each page with full template context.
    for rec in records:
        toc_html = render_toc(rec["headings"])
        updated_html = ""
        date = last_updated(src, rec["rel"], last_updated_mode)
        if date:
            updated_html = (
                f'<div class="page-updated">Last updated: '
                f'<time datetime="{date}">{date}</time></div>'
            )
        nb = neighbors.get(rec["url"], {"prev": None, "next": None})
        prev_next_html = render_prev_next(nb["prev"], nb["next"], base)
        page_html = render_page(
            page_title=f'{rec["title"]} · {site_title}' if rec["title"] != site_title else site_title,
            site_title=site_title,
            description=description,
            content=rec["html"],
            nav_html=nav_html,
            toc_html=toc_html,
            prev_next_html=prev_next_html,
            footer=footer,
            theme=theme,
            base=base,
            live_reload=live_reload,
            head_extra=head_extra,
            logo_html=logo_html,
            updated_html=updated_html,
        )
        out_abs = out / rec["out_rel"]
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        out_abs.write_text(page_html, encoding="utf-8")

    # 404 page: most static hosts serve /404.html automatically on a miss.
    # Asset/nav links carry the base prefix like every other page.
    if config.get("error_page", True):
        not_found = render_page(
            page_title=f"404 · {site_title}",
            site_title=site_title,
            description=description,
            content=(
                '<h1>Page not found</h1>\n'
                '<p>The page you’re looking for doesn’t exist or may have moved.</p>\n'
                f'<p><a href="{base}">← Back to home</a></p>'
            ),
            nav_html=nav_html,
            toc_html="",
            prev_next_html=render_prev_next(None, None, base),
            footer=footer,
            theme=theme,
            base=base,
            live_reload=live_reload,
            head_extra=head_extra,
            logo_html=logo_html,
        )
        (out / "404.html").write_text(not_found, encoding="utf-8")

    # Copy static assets verbatim.
    for rel in assets:
        if rel == "mdsite.config.json":
            continue
        out_abs = out / rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, out_abs)

    # Optional user CSS, appended to the bundled stylesheet (its rules win).
    extra_css = ""
    custom_css = config.get("custom_css")
    if custom_css:
        css_path = src / custom_css
        try:
            extra_css = css_path.read_text(encoding="utf-8")
        except OSError:
            print(f"warn: custom_css file not found: {custom_css} — skipping")

    # Bundled CSS/JS assets + search index + sitemap.
    write_assets(out, extra_css=extra_css)
    write_search_index(out, records)
    write_sitemap(out, [r["url"] for r in records], base)

    if config.get("check_links", True) and broken_links:
        print(f"warn: {len(broken_links)} broken internal link(s):")
        for source_rel, href in broken_links:
            print(f"  {source_rel} -> {href}")

    print(f"Built {len(records)} page(s) -> {out}")
    return {
        "page_count": len(records),
        "out": str(out),
        "broken_links": broken_links,
    }
