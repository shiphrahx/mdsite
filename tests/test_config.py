"""Tests for config loading + exclude-glob matching."""

from __future__ import annotations

import json

from mdsite.config import DEFAULTS, load_config, make_exclude_matcher


# ---- load_config ----

def test_missing_config_returns_defaults(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg == DEFAULTS
    # Returns a copy, not the shared module dict.
    cfg["title"] = "mutated"
    assert DEFAULTS["title"] is None


def test_config_merges_over_defaults(tmp_path):
    (tmp_path / "mdsite.config.json").write_text(
        json.dumps({"title": "My Site", "footer": "© Me"}), encoding="utf-8"
    )
    cfg = load_config(tmp_path)
    assert cfg["title"] == "My Site"
    assert cfg["footer"] == "© Me"
    # Untouched keys keep defaults.
    assert cfg["theme"] == "auto"
    assert cfg["exclude"] == []


def test_malformed_config_warns_and_defaults(tmp_path, capsys):
    (tmp_path / "mdsite.config.json").write_text("{ not valid json ", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg == DEFAULTS
    assert "malformed" in capsys.readouterr().out


# ---- exclude matcher ----

def test_double_star_matches_nested():
    m = make_exclude_matcher(["drafts/**"])
    assert m("drafts/secret.md")
    assert m("drafts/a/b/c.md")
    assert not m("public/notes.md")


def test_single_star_is_segment_local():
    m = make_exclude_matcher(["*.tmp.md"])
    assert m("notes.tmp.md")
    assert not m("sub/notes.tmp.md")  # * does not cross /


def test_question_mark_single_char():
    m = make_exclude_matcher(["?.md"])
    assert m("a.md")
    assert not m("ab.md")
    assert not m("/.md".lstrip("/"))


def test_special_chars_escaped():
    m = make_exclude_matcher(["a.b.md"])
    assert m("a.b.md")
    assert not m("axbymd")  # dots are literal, not wildcards


def test_multiple_patterns_any_match():
    m = make_exclude_matcher(["private/**", "*.tmp.md"])
    assert m("private/x.md")
    assert m("scratch.tmp.md")
    assert not m("keep.md")


def test_empty_patterns_match_nothing():
    m = make_exclude_matcher([])
    assert not m("anything.md")
    m2 = make_exclude_matcher(None)
    assert not m2("anything.md")


def test_backslash_path_normalized():
    m = make_exclude_matcher(["drafts/**"])
    assert m("drafts\\win\\path.md")


def test_anchored_full_match_required():
    m = make_exclude_matcher(["notes.md"])
    assert m("notes.md")
    assert not m("my-notes.md")  # must match whole path
    assert not m("notes.md.bak")
