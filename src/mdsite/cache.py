"""Content-hash render cache for incremental builds.

render() (markdown-it parse + Pygments highlight) is the build's hot path. We
cache its result per page keyed by a hash of the page content plus a build
signature (feature flags + the full url map). When nothing structural changes,
editing one page leaves every other page's cache entry valid, so only the
edited page is re-rendered.

The cache lives OUTSIDE the output directory so it survives `mdsite serve`'s
clean rebuilds (where it matters most)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .render import Heading


def encode_headings(headings: list[Heading]) -> list[list]:
    return [[h.level, h.text, h.slug] for h in headings]


def decode_headings(data: list[list]) -> list[Heading]:
    return [Heading(level=int(lv), text=t, slug=s) for lv, t, s in data]


def cache_path_for(out: Path) -> Path:
    """Cache file sibling to the output dir (e.g. dist -> dist.mdsite-cache.json)."""
    return out.parent / f"{out.name}.mdsite-cache.json"


class RenderCache:
    """Maps content-hash -> {html, headings, broken}. `old` is last build's
    cache; `new` accumulates this build's entries and is written on save()."""

    def __init__(self, path: Path, active: bool):
        self.path = path
        self.active = active
        self.old: dict = {}
        self.new: dict = {}
        self.hits = 0
        self.misses = 0
        if active:
            try:
                self.old = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.old = {}

    @staticmethod
    def key(content: str, signature: str) -> str:
        h = hashlib.sha256()
        h.update(signature.encode("utf-8"))
        h.update(b"\x00")
        h.update(content.encode("utf-8"))
        return h.hexdigest()

    def get(self, key: str):
        if not self.active:
            return None
        entry = self.old.get(key)
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry

    def put(self, key: str, html: str, headings: list[Heading],
            broken: list[str]) -> None:
        if not self.active:
            return
        self.new[key] = {
            "html": html,
            "headings": encode_headings(headings),
            "broken": broken,
        }

    def save(self) -> None:
        if not self.active:
            return
        try:
            self.path.write_text(
                json.dumps(self.new, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as err:  # noqa: BLE001
            print(f"warn: could not write build cache: {err}")
