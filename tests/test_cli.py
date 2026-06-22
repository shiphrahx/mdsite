"""Tests for CLI argument parsing + command dispatch."""

from __future__ import annotations

import pytest

from mdsite.cli import build_parser, main


# ---- parser ----

def test_build_args_defaults():
    args = build_parser().parse_args(["build", "src"])
    assert args.command == "build"
    assert args.srcDir == "src"
    assert args.out == "./dist"
    assert args.base == "/"
    assert args.clean is False
    assert args.title is None


def test_build_args_flags():
    args = build_parser().parse_args(
        ["build", "docs", "-o", "out", "-t", "T", "--clean", "--base", "/d/"]
    )
    assert args.out == "out"
    assert args.title == "T"
    assert args.clean is True
    assert args.base == "/d/"


def test_serve_args_port_default():
    args = build_parser().parse_args(["serve", "src"])
    assert args.command == "serve"
    assert args.port == 3000


def test_serve_args_port_custom():
    args = build_parser().parse_args(["serve", "src", "--port", "8080"])
    assert args.port == 8080


def test_init_args_default_dir():
    args = build_parser().parse_args(["init"])
    assert args.command == "init"
    assert args.dir == "."


def test_init_args_custom_dir():
    args = build_parser().parse_args(["init", "mysite"])
    assert args.dir == "mysite"


# ---- dispatch ----

def test_no_command_prints_help_returns_1(capsys):
    assert main([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_dispatch_build(monkeypatch):
    calls = {}

    def fake_build(src, opts, *a, **k):
        calls["src"] = src
        calls["opts"] = opts

    monkeypatch.setattr("mdsite.build.build", fake_build)
    rc = main(["build", "src", "--base", "/d/", "-t", "Title", "--clean"])
    assert rc == 0
    assert calls["src"] == "src"
    assert calls["opts"]["base"] == "/d/"
    assert calls["opts"]["title"] == "Title"
    assert calls["opts"]["clean"] is True


def test_dispatch_serve_passes_port(monkeypatch):
    calls = {}

    def fake_serve(src, opts, *a, **k):
        calls["src"] = src
        calls["opts"] = opts

    monkeypatch.setattr("mdsite.serve.serve", fake_serve)
    rc = main(["serve", "src", "--port", "9999"])
    assert rc == 0
    assert calls["opts"]["port"] == 9999


def test_dispatch_init(monkeypatch):
    calls = {}
    monkeypatch.setattr("mdsite.init.init", lambda d: calls.setdefault("dir", d))
    rc = main(["init", "out"])
    assert rc == 0
    assert calls["dir"] == "out"
