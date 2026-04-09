"""CLI entry point: python -m sync2cf <repo-path>"""

from __future__ import annotations

import argparse
import logging
import sys
from importlib import resources
from pathlib import Path

import md2cf.document

from sync2cf.config import Sync2CfContext, Sync2CfSettings
from sync2cf.confluence import run_sync
from sync2cf.git_info import get_git_info
from sync2cf.postface import render_postface

log = logging.getLogger("sync2cf")

# ── Bundled assets inside the package ─────────────────────────────────────
_PACKAGE_FILES = resources.files("sync2cf")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sync2cf",
        description="Sync markdown files from a git repo to Confluence.",
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Root directory of the git working tree to sync.",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Print what would be done without calling the Confluence API.",
    )
    parser.add_argument(
        "--space",
        type=str,
        default=None,
        help="Override the Confluence space key (default: from CONFLUENCE_SPACE env var).",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Override auto-detected prefix (default: branch name on non-prod).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
    )

    repo_path = args.repo_path.resolve()
    if not repo_path.is_dir():
        log.error("Not a directory: %s", repo_path)
        sys.exit(1)

    # ── Load settings from env / .env ─────────────────────────────────
    settings = Sync2CfSettings()

    # ── Git state ─────────────────────────────────────────────────────
    git_info = get_git_info(repo_path)

    log.info(
        "Git: branch=%s default=%s clean=%s up_to_date=%s → use_prod=%s",
        git_info.branch_name,
        git_info.default_branch,
        git_info.is_clean,
        git_info.is_up_to_date,
        git_info.use_prod,
    )

    # ── Build runtime context ─────────────────────────────────────────
    use_prod = git_info.use_prod
    branch_name = git_info.branch_name

    # CLI overrides
    if args.prefix is not None:
        # Explicit prefix → force int mode
        branch_name = args.prefix
        if args.prefix == "":
            use_prod = True  # empty prefix = prod behaviour

    ctx = Sync2CfContext(
        settings,
        repo_path=repo_path,
        use_prod=use_prod,
        branch_name=branch_name,
        dry_run=args.dry_run,
    )

    if args.space:
        ctx.space = args.space

    # ── Preface / postface markup ─────────────────────────────────────
    preface_markup = ""
    preface_ref = _PACKAGE_FILES.joinpath("preface.md")
    if preface_ref.is_file():
        preface_markup = md2cf.document.parse_page(
            [preface_ref.read_text(encoding="utf-8")]
        ).body

    postface_markup = ""
    postface_ref = _PACKAGE_FILES.joinpath("postface.md.template")
    if postface_ref.is_file():
        postface_md = render_postface(
            postface_ref.read_text(encoding="utf-8"), git_info
        )
        postface_markup = md2cf.document.parse_page([postface_md]).body

    # ── Run ───────────────────────────────────────────────────────────
    run_sync(ctx, preface_markup, postface_markup)


if __name__ == "__main__":
    main()
