"""Load mdsite.config.json + exclude-glob matching."""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULTS = {
    "title": None,
    "description": "",
    "theme": "auto",  # "light" | "dark" | "auto"
    "footer": "",
    "exclude": [],
    "custom_css": None,  # path (relative to source) to a CSS file appended to style.css
}


def load_config(src_dir: Path) -> dict:
    """Merge mdsite.config.json over defaults. Missing -> defaults.
    Malformed JSON -> warn, defaults."""
    file = Path(src_dir) / "mdsite.config.json"
    try:
        raw = file.read_text(encoding="utf-8")
    except OSError:
        return dict(DEFAULTS)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        print(f"warn: malformed mdsite.config.json — ignoring ({err})")
        return dict(DEFAULTS)
    return {**DEFAULTS, **parsed}


def _glob_to_regex(glob: str) -> re.Pattern:
    """Compile a glob (**, *, ?) into a regex matching forward-slash paths."""
    out: list[str] = []
    i = 0
    n = len(glob)
    while i < n:
        c = glob[i]
        if c == "*":
            if i + 1 < n and glob[i + 1] == "*":
                out.append(".*")
                i += 1
                if i + 1 < n and glob[i + 1] == "/":
                    i += 1
            else:
                out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c in ".+^${}()|[]\\":
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return re.compile("^" + "".join(out) + "$")


def make_exclude_matcher(patterns: list[str] | None = None):
    """Return predicate: True if a relative path matches any pattern."""
    regexes = [_glob_to_regex(p) for p in (patterns or [])]

    def matches(rel_path: str) -> bool:
        norm = rel_path.replace("\\", "/")
        return any(r.match(norm) for r in regexes)

    return matches
