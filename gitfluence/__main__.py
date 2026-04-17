"""CLI entry point: python -m gitfluence <repo-path>"""

from __future__ import annotations

import argparse
import logging
import sys
from importlib import resources
from pathlib import Path

import mdfluence.document

from gitfluence.config import GitfluenceContext, GitfluenceSettings
from gitfluence.confluence import run_sync
from gitfluence.git_info import get_git_info
from gitfluence.postface import render_postface

log = logging.getLogger("gitfluence")

# ── Bundled assets inside the package ─────────────────────────────────────
_PACKAGE_FILES = resources.files("gitfluence")


def main(  # pylint: disable=too-many-locals,too-many-statements
    argv: list[str] | None = None,
) -> None:
    parser = argparse.ArgumentParser(
        prog="gitfluence",
        description="Sync markdown files from a git repo to Confluence.",
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Root directory of the git working tree to sync.",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--only-changed",
        action="store_true",
        default=True,
        help="Only update pages whose content has changed (default: True).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retries for Confluence API calls (default: 3).",
    )
    # ── Page information arguments ────────────────────────────────────
    page_group = parser.add_argument_group("page information arguments")
    page_group.add_argument(
        "-t", "--title", type=str, default=None, help="Set the page title."
    )
    page_group.add_argument(
        "-c",
        "--content-type",
        type=str,
        default="page",
        help="Content type (default: page).",
    )
    page_group.add_argument(
        "-m", "--message", type=str, default=None, help="Version message for the page."
    )
    page_group.add_argument(
        "--minor-edit",
        action="store_true",
        help="Mark the edit as a minor edit.",
    )
    page_group.add_argument(
        "--strip-top-header",
        action="store_true",
        default=True,
        help="Strip the top-level header from pages (default: True).",
    )
    page_group.add_argument(
        "--remove-text-newlines",
        action="store_true",
        help="Remove newlines from text nodes.",
    )
    page_group.add_argument(
        "--replace-all-labels",
        action="store_true",
        help="Replace all existing labels on the page.",
    )

    parent_group = page_group.add_mutually_exclusive_group()
    parent_group.add_argument(
        "-a", "--parent-title", type=str, default=None, help="Parent page title."
    )
    parent_group.add_argument(
        "-A", "--parent-id", type=str, default=None, help="Parent page ID."
    )
    parent_group.add_argument(
        "--top-level",
        action="store_true",
        help="Create pages as top-level children of the space.",
    )

    preface_group = page_group.add_mutually_exclusive_group()
    preface_group.add_argument(
        "--preface-markdown",
        type=str,
        default=None,
        help="Markdown string to prepend to every page.",
    )
    preface_group.add_argument(
        "--preface-file",
        type=Path,
        default=None,
        help="Markdown file to prepend to every page.",
    )

    postface_group = page_group.add_mutually_exclusive_group()
    postface_group.add_argument(
        "--postface-markdown",
        type=str,
        default=None,
        help="Markdown string to append to every page.",
    )
    postface_group.add_argument(
        "--postface-file",
        type=Path,
        default=None,
        help="Markdown file to append to every page.",
    )

    # ── Directory arguments ───────────────────────────────────────────
    dir_group = parser.add_argument_group("directory arguments")
    dir_group.add_argument(
        "--collapse-single-pages",
        action="store_true",
        default=True,
        help="Collapse directories with a single page (default: True).",
    )
    dir_group.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not use .gitignore to filter files.",
    )
    dir_group.add_argument(
        "--skip-subtrees-wo-markdown",
        action="store_true",
        default=True,
        help="Skip directory subtrees without markdown files (default: True).",
    )

    dir_title_group = dir_group.add_mutually_exclusive_group()
    dir_title_group.add_argument(
        "--beautify-folders",
        action="store_true",
        help="Beautify folder names (capitalize, replace dashes/underscores).",
    )
    dir_title_group.add_argument(
        "--use-pages-file",
        action="store_true",
        help="Use .pages files for directory titles and ordering.",
    )

    empty_group = dir_group.add_mutually_exclusive_group()
    empty_group.add_argument(
        "--collapse-empty",
        action="store_true",
        help="Collapse empty directories.",
    )
    empty_group.add_argument(
        "--skip-empty",
        action="store_true",
        default=True,
        help="Skip empty directories (default: True).",
    )

    # ── Relative links arguments ──────────────────────────────────────
    links_group = parser.add_argument_group("relative links arguments")
    links_group.add_argument(
        "--enable-relative-links",
        action="store_true",
        default=True,
        help="Enable relative link resolution (default: True).",
    )
    links_group.add_argument(
        "--ignore-relative-link-errors",
        action="store_true",
        help="Ignore errors from unresolvable relative links.",
    )

    # ── Anchor arguments ──────────────────────────────────────────────
    anchor_group = parser.add_argument_group("anchor arguments")
    anchor_group.add_argument(
        "--convert-anchors",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Convert markdown anchors to Confluence format (default: True).",
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
    settings = GitfluenceSettings()

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

    ctx = GitfluenceContext(
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
    if args.preface_markdown:
        preface_markup = mdfluence.document.parse_page(  # pylint: disable=no-member
            [args.preface_markdown]
        ).body
    elif args.preface_file:
        preface_markup = mdfluence.document.parse_page(  # pylint: disable=no-member
            [args.preface_file.read_text(encoding="utf-8")]
        ).body
    else:
        preface_ref = _PACKAGE_FILES.joinpath("preface.md")
        if preface_ref.is_file():
            preface_markup = mdfluence.document.parse_page(  # pylint: disable=no-member
                [preface_ref.read_text(encoding="utf-8")]
            ).body

    postface_markup = ""
    if args.postface_markdown:
        postface_markup = mdfluence.document.parse_page(  # pylint: disable=no-member
            [args.postface_markdown]
        ).body
    elif args.postface_file:
        postface_markup = mdfluence.document.parse_page(  # pylint: disable=no-member
            [args.postface_file.read_text(encoding="utf-8")]
        ).body
    else:
        postface_ref = _PACKAGE_FILES.joinpath("postface.md.template")
        if postface_ref.is_file():
            postface_md = render_postface(
                postface_ref.read_text(encoding="utf-8"), git_info
            )
            postface_markup = (
                mdfluence.document.parse_page(  # pylint: disable=no-member
                    [postface_md]
                ).body
            )

    # ── Run ───────────────────────────────────────────────────────────
    run_sync(ctx, preface_markup, postface_markup, args=args)


if __name__ == "__main__":
    main()
