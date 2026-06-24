"""Tests for the incremental render cache."""

from __future__ import annotations

from mdsite.cache import (
    RenderCache,
    cache_path_for,
    decode_headings,
    encode_headings,
)
from mdsite.render import Heading


def test_heading_roundtrip():
    hs = [Heading(2, "Install", "install"), Heading(3, "Steps", "steps")]
    assert decode_headings(encode_headings(hs)) == hs


def test_cache_path_sibling_of_out(tmp_path):
    out = tmp_path / "dist"
    assert cache_path_for(out) == tmp_path / "dist.mdsite-cache.json"


def test_inactive_cache_is_noop(tmp_path):
    c = RenderCache(tmp_path / "c.json", active=False)
    k = c.key("content", "sig")
    assert c.get(k) is None
    c.put(k, "<p>x</p>", [], [])
    c.save()
    assert not (tmp_path / "c.json").exists()


def test_active_cache_persists_and_reloads(tmp_path):
    path = tmp_path / "c.json"
    c1 = RenderCache(path, active=True)
    k = c1.key("hello", "sig-v1")
    assert c1.get(k) is None  # miss
    c1.put(k, "<p>hello</p>", [Heading(2, "H", "h")], ["./broken.md"])
    c1.save()
    assert path.exists()

    c2 = RenderCache(path, active=True)
    entry = c2.get(k)
    assert entry is not None  # hit on reload
    assert entry["html"] == "<p>hello</p>"
    assert entry["broken"] == ["./broken.md"]
    assert decode_headings(entry["headings"]) == [Heading(2, "H", "h")]
    assert c2.hits == 1


def test_key_changes_with_content_and_signature():
    c = RenderCache(None, active=False)
    assert c.key("a", "s") != c.key("b", "s")
    assert c.key("a", "s1") != c.key("a", "s2")
    assert c.key("a", "s") == c.key("a", "s")
