"""Tests for versioned-docs helpers."""

from __future__ import annotations

import pytest

from mdsite.versions import (
    default_version,
    normalize_versions,
    redirect_html,
    render_version_switcher,
)


# ---- normalize_versions ----

def test_normalize_dicts_with_explicit_default():
    versions = normalize_versions([
        {"label": "v1", "dir": "v1"},
        {"label": "v2 latest", "dir": "v2", "default": True},
    ])
    assert [v["slug"] for v in versions] == ["v1", "v2-latest"]
    assert default_version(versions)["dir"] == "v2"


def test_normalize_defaults_to_first():
    versions = normalize_versions([{"label": "A", "dir": "a"}, "b"])
    assert versions[0]["default"] is True
    assert versions[1]["default"] is False
    # Bare-string shorthand.
    assert versions[1] == {"label": "b", "dir": "b", "slug": "b", "default": False}


def test_normalize_keeps_only_first_default():
    versions = normalize_versions([
        {"label": "a", "dir": "a", "default": True},
        {"label": "b", "dir": "b", "default": True},
    ])
    assert [v["default"] for v in versions] == [True, False]


def test_normalize_rejects_empty():
    with pytest.raises(ValueError):
        normalize_versions([])
    with pytest.raises(ValueError):
        normalize_versions("nope")


# ---- render_version_switcher ----

def test_switcher_marks_current_and_links():
    versions = normalize_versions(["v1", "v2"])
    html = render_version_switcher(versions, "v2", "/docs/")
    assert '<div class="version-switcher">' in html
    assert '<option value="/docs/v1/">v1</option>' in html
    assert '<option value="/docs/v2/" selected>v2</option>' in html


# ---- redirect_html ----

def test_redirect_html():
    html = redirect_html("/docs/v2/")
    assert 'http-equiv="refresh"' in html
    assert 'url=/docs/v2/' in html
    assert 'href="/docs/v2/"' in html
