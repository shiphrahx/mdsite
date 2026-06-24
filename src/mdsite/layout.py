"""HTML template assembly: page shell, nav tree, TOC, prev/next."""

from __future__ import annotations

from html import escape
from importlib import resources
from pathlib import Path

from .nav import NavNode
from .render import Heading, pygments_css

_TEMPLATE_FILES = ("page.html", "style.css", "app.js", "search.js")


def _load(name: str) -> str:
    return resources.files("mdsite").joinpath("templates", name).read_text(encoding="utf-8")


_PAGE = _load("page.html")


def render_nav(tree: NavNode, base: str) -> str:
    """Render the sidebar nav tree as nested <ul>, once for the whole site.
    The current page is highlighted client-side (app.js matches the URL), so
    this output is identical on every page and can be computed a single time."""

    def render_node(node: NavNode, path: str) -> str:
        items: list[str] = []
        # Folders render as collapsible groups; pages as plain links.
        for child in node.children:
            child_path = f"{path}/{child.name}" if path else child.name
            label_url = child.url
            label = escape(child.title or child.name)
            inner = render_node(child, child_path)
            if label_url:
                label_html = f'<a class="folder-link" href="{label_url}">{label}</a>'
            else:
                label_html = f'<span class="folder-name">{label}</span>'
            items.append(
                f'<li class="nav-folder" data-path="{escape(child_path)}">'
                f'<div class="folder-label"><span class="caret">▾</span>{label_html}</div>'
                f"{inner}</li>"
            )
        for page in node.pages:
            items.append(
                f'<li><a href="{page.url}">{escape(page.title)}</a></li>'
            )
        if not items:
            return ""
        return "<ul>" + "".join(items) + "</ul>"

    return render_node(tree, "")


def render_toc(headings: list[Heading]) -> str:
    """Right-sidebar TOC from H2/H3. Empty if fewer than 2 headings total."""
    relevant = [h for h in headings if h.level in (2, 3)]
    if len(headings) < 2 or not relevant:
        return ""
    items = ['<div class="toc-title">On this page</div>', "<ul>"]
    for h in relevant:
        cls = "toc-h3" if h.level == 3 else "toc-h2"
        items.append(f'<li><a class="{cls}" href="#{h.slug}">{escape(h.text)}</a></li>')
    items.append("</ul>")
    return "".join(items)


def render_prev_next(prev, nxt, base: str) -> str:
    parts: list[str] = []
    if prev:
        parts.append(
            f'<a class="pn-prev" href="{prev.url}">'
            f'<span class="pn-dir">← Previous</span>'
            f'<span class="pn-title">{escape(prev.title)}</span></a>'
        )
    else:
        parts.append("<span></span>")
    if nxt:
        parts.append(
            f'<a class="pn-next" href="{nxt.url}">'
            f'<span class="pn-dir">Next →</span>'
            f'<span class="pn-title">{escape(nxt.title)}</span></a>'
        )
    else:
        parts.append("<span></span>")
    return "".join(parts)


def render_page(*, page_title, site_title, description, content, nav_html,
                toc_html, prev_next_html, footer, theme, base, live_reload="",
                head_extra="", logo_html="", updated_html="", tags_html="",
                body_extra="") -> str:
    return _PAGE.format(
        page_title=escape(page_title),
        site_title=escape(site_title),
        description=escape(description or ""),
        content=content,
        nav_html=nav_html,
        toc_html=toc_html,
        prev_next_html=prev_next_html,
        footer=footer or "",
        theme=escape(theme or "auto"),
        base=base,
        live_reload=live_reload,
        head_extra=head_extra or "",
        logo_html=logo_html or "",
        updated_html=updated_html or "",
        tags_html=tags_html or "",
        body_extra=body_extra or "",
    )


def write_vendor_asset(out_dir: Path, name: str) -> str:
    """Copy a bundled third-party asset (templates/vendor/<name>) into
    out/assets/vendor/. Returns the output-relative path under assets/."""
    data = resources.files("mdsite").joinpath("templates", "vendor", name).read_bytes()
    dest = out_dir / "assets" / "vendor"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / name).write_bytes(data)
    return f"assets/vendor/{name}"


def _copy_traversable(trav, dest: Path) -> None:
    if trav.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in trav.iterdir():
            _copy_traversable(child, dest / child.name)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(trav.read_bytes())


def write_vendor_tree(out_dir: Path, subdir: str) -> str:
    """Recursively copy a bundled vendor directory (templates/vendor/<subdir>)
    into out/assets/vendor/<subdir>. Returns the output-relative root path."""
    root = resources.files("mdsite").joinpath("templates", "vendor", subdir)
    _copy_traversable(root, out_dir / "assets" / "vendor" / subdir)
    return f"assets/vendor/{subdir}"


def render_meta_tags(*, title, description, url=None, image=None,
                     site_title=None, og_type="website") -> str:
    """Open Graph + Twitter Card <meta> tags for social sharing. Only emits a
    tag when its value is present. Returns a newline-joined string (or '')."""
    tags: list[str] = []

    def meta(prop_attr, prop, content):
        if content:
            tags.append(
                f'<meta {prop_attr}="{escape(prop, quote=True)}" '
                f'content="{escape(str(content), quote=True)}">'
            )

    meta("property", "og:title", title)
    meta("property", "og:description", description)
    meta("property", "og:type", og_type)
    meta("property", "og:url", url)
    meta("property", "og:image", image)
    meta("property", "og:site_name", site_title)
    # Twitter falls back to og:* but card type + image type must be explicit.
    meta("name", "twitter:card", "summary_large_image" if image else "summary")
    meta("name", "twitter:title", title)
    meta("name", "twitter:description", description)
    meta("name", "twitter:image", image)
    return "\n".join(tags)


def write_assets(out_dir: Path, pygments_style: str = "default",
                 extra_css: str = "") -> None:
    """Copy static template assets + generated highlight CSS into out/assets/.

    extra_css (e.g. a user's custom.css) is appended last so its rules win over
    the bundled defaults — letting users rebrand without forking templates."""
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    # Append Pygments CSS to style.css so it ships as one file.
    style = _load("style.css") + "\n\n/* Syntax highlighting (Pygments) */\n" + pygments_css(pygments_style)
    if extra_css:
        style += "\n\n/* Custom CSS (user override) */\n" + extra_css
    (assets / "style.css").write_text(style, encoding="utf-8")
    (assets / "app.js").write_text(_load("app.js"), encoding="utf-8")
    (assets / "search.js").write_text(_load("search.js"), encoding="utf-8")
