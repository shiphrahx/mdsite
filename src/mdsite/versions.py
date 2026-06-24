"""Versioned-docs helpers: normalize the `versions` config and render the
header version switcher.

`versions` is a list of entries describing documentation versions, each a
subdirectory of the source root:

    "versions": [
      {"label": "v2 (latest)", "dir": "v2", "default": true},
      {"label": "v1", "dir": "v1"}
    ]

A bare string entry is shorthand for {"label": s, "dir": s}."""

from __future__ import annotations

from html import escape

from .render import slugify


def normalize_versions(value) -> list[dict]:
    """Return a list of {label, dir, slug, default} from the config value.

    Exactly one entry is flagged default: the one marked `default: true`, else
    the first. Raises ValueError on an empty/invalid list."""
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("`versions` must be a non-empty list")
    out: list[dict] = []
    for entry in value:
        if isinstance(entry, str):
            label, directory, default = entry, entry, False
        elif isinstance(entry, dict):
            label = str(entry.get("label") or entry.get("dir") or "")
            directory = str(entry.get("dir") or entry.get("label") or "")
            default = bool(entry.get("default", False))
        else:
            raise ValueError(f"invalid version entry: {entry!r}")
        if not label or not directory:
            raise ValueError(f"version entry needs a label and dir: {entry!r}")
        out.append({"label": label, "dir": directory,
                    "slug": slugify(label), "default": default})
    if not any(v["default"] for v in out):
        out[0]["default"] = True
    else:
        # Keep only the first explicit default to avoid ambiguity.
        seen = False
        for v in out:
            if v["default"] and not seen:
                seen = True
            else:
                v["default"] = False
    return out


def default_version(versions: list[dict]) -> dict:
    return next(v for v in versions if v["default"])


def render_version_switcher(versions: list[dict], current_slug: str, base: str) -> str:
    """Render a <select> linking to each version's home (current one selected)."""
    options = []
    for v in versions:
        sel = " selected" if v["slug"] == current_slug else ""
        url = f"{base}{v['slug']}/"
        options.append(
            f'<option value="{escape(url, quote=True)}"{sel}>'
            f'{escape(v["label"])}</option>'
        )
    return (
        '<div class="version-switcher">'
        '<select aria-label="Select documentation version">'
        + "".join(options) +
        "</select></div>"
    )


def redirect_html(target: str) -> str:
    """A minimal HTML page that redirects the browser to `target`."""
    t = escape(target, quote=True)
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        f'<meta http-equiv="refresh" content="0; url={t}">'
        f'<link rel="canonical" href="{t}">'
        f'<title>Redirecting…</title></head>'
        f'<body><p>Redirecting to <a href="{t}">{escape(target)}</a>…</p></body></html>\n'
    )
