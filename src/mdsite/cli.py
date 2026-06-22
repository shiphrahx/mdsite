"""Command-line interface: argument parsing + command dispatch."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdsite",
        description="Turn a folder of Markdown files into a clean static HTML site.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # Shared build-time options, attached to commands that build.
    def add_build_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("-o", "--out", default="./dist",
                       help="Output directory (default: ./dist)")
        p.add_argument("-t", "--title", default=None,
                       help="Site title (default: from config or folder name)")
        p.add_argument("--clean", action="store_true",
                       help="Wipe the output dir before building")
        p.add_argument("--base", default="/",
                       help="Base URL path for hosting in a subfolder (default: /)")

    p_build = sub.add_parser("build", help="Build a site from a folder of .md files")
    p_build.add_argument("srcDir", help="Folder of .md files")
    add_build_opts(p_build)

    p_serve = sub.add_parser("serve", help="Build, then serve locally + live-reload")
    p_serve.add_argument("srcDir", help="Folder of .md files")
    add_build_opts(p_serve)
    p_serve.add_argument("--port", type=int, default=3000,
                         help="Preferred port (default: 3000)")

    p_init = sub.add_parser("init", help="Create a sample content folder + config")
    p_init.add_argument("dir", nargs="?", default=".",
                        help="Target directory (default: current dir)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    opts = {
        "out": getattr(args, "out", "./dist"),
        "title": getattr(args, "title", None),
        "clean": getattr(args, "clean", False),
        "base": getattr(args, "base", "/"),
    }

    if args.command == "build":
        from .build import build
        build(args.srcDir, opts)
        return 0

    if args.command == "serve":
        from .serve import serve
        opts["port"] = args.port
        serve(args.srcDir, opts)
        return 0

    if args.command == "init":
        from .init import init
        init(args.dir)
        return 0

    parser.print_help()
    return 1


def _entry() -> None:
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as err:  # noqa: BLE001 — top-level friendly error
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _entry()
