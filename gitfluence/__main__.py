"""CLI entry point: python -m gitfluence <repo-path>"""

from __future__ import annotations

import argparse
import logging
import sys
from importlib import resources
from pathlib import Path

import mdfluence.document
from mdfluence.__main__ import get_parser

from gitfluence.config import GitfluenceContext, GitfluenceSettings
from gitfluence.confluence import run_sync
from gitfluence.git_info import get_git_info
from gitfluence.template import render_template

log = logging.getLogger("gitfluence")

# ── Bundled assets inside the package ─────────────────────────────────────
_PACKAGE_FILES = resources.files("gitfluence")


def _remove_action(parser: argparse.ArgumentParser, dest: str) -> None:
    """Remove an action from a parser by its dest name."""
    for action in parser._actions[:]:
        if action.dest == dest:
            parser._actions.remove(action)
            # Remove from option_string_actions mapping
            for opt in action.option_strings:
                parser._option_string_actions.pop(opt, None)
            for group in parser._action_groups:
                if action in group._group_actions:
                    group._group_actions.remove(action)
            # Remove from mutually exclusive groups; prune empty ones
            for mutex in parser._mutually_exclusive_groups[:]:
                if action in mutex._group_actions:
                    mutex._group_actions.remove(action)
                    if not mutex._group_actions:
                        parser._mutually_exclusive_groups.remove(mutex)
            break


def _find_action(parser: argparse.ArgumentParser, dest: str) -> argparse.Action | None:
    """Find an action by its dest name."""
    for action in parser._actions:
        if action.dest == dest:
            return action
    return None


def _build_parser() -> argparse.ArgumentParser:
    """Build gitfluence CLI parser inheriting mdfluence's parser."""
    parser = get_parser()
    parser.prog = "gitfluence"
    parser.description = "Sync markdown files from a git repo to Confluence."

    # ── Remove mdfluence-only args ────────────────────────────────────
    _remove_action(parser, "file_list")
    _remove_action(parser, "output")

    # Remove preface/postface (nargs="?" conflict) — will re-add below
    for dest in (
        "preface_markdown",
        "preface_file",
        "postface_markdown",
        "postface_file",
    ):
        _remove_action(parser, dest)

    # Remove mdfluence --prefix (different semantics) — will re-add below
    _remove_action(parser, "prefix")

    # ── Null out mdfluence env var defaults (gitfluence uses pydantic-settings) ──
    parser.set_defaults(
        host=None,
        token=None,
        username=None,
        password=None,
        space=None,
    )

    # ── Override mdfluence defaults (sync-oriented) ───────────────────
    parser.set_defaults(
        only_changed=True,
        strip_top_header=True,
        collapse_single_pages=True,
        skip_empty=True,
        skip_subtrees_wo_markdown=True,
        enable_relative_links=True,
    )

    # ── Repurpose --debug as alias for --verbose ──────────────────────
    _remove_action(parser, "debug")
    parser.add_argument(
        "-v",
        "--verbose",
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    # ── Add -n alias to --dry-run ─────────────────────────────────────
    dry_run_action = _find_action(parser, "dry_run")
    if dry_run_action and "-n" not in dry_run_action.option_strings:
        dry_run_action.option_strings = ["-n", *dry_run_action.option_strings]
        parser._option_string_actions["-n"] = dry_run_action

    # ── Add positional repo_path ──────────────────────────────────────
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Root directory of the git working tree to sync.",
    )

    # ── Add gitfluence-specific args ──────────────────────────────────
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Override auto-detected prefix (default: branch name on non-prod).",
    )

    # ── Preface group (re-added with gitfluence semantics) ────────────
    page_group = None
    for group in parser._action_groups:
        if group.title == "page information arguments":
            page_group = group
            break
    if page_group is None:
        page_group = parser.add_argument_group("page information arguments")

    preface_group = page_group.add_mutually_exclusive_group()
    preface_group.add_argument(
        "--preface-markdown",
        type=str,
        default=None,
        help="Markdown template string to prepend to every page. "
        "Supports {branch_name}, {repo_origin}, {username}, {hostname}, {timestamp} placeholders.",
    )
    preface_group.add_argument(
        "--preface-file",
        type=Path,
        default=None,
        help="Markdown template file to prepend to every page.",
    )
    preface_group.add_argument(
        "--no-preface",
        action="store_true",
        help="Disable the default preface (DO-NOT-EDIT banner).",
    )

    postface_group = page_group.add_mutually_exclusive_group()
    postface_group.add_argument(
        "--postface-markdown",
        type=str,
        default=None,
        help="Markdown template string to append to every page.",
    )
    postface_group.add_argument(
        "--postface-file",
        type=Path,
        default=None,
        help="Markdown template file to append to every page.",
    )
    postface_group.add_argument(
        "--no-postface",
        action="store_true",
        help="Disable the default postface (metadata footer).",
    )

    # ── Integration target args ───────────────────────────────────────
    int_group = parser.add_argument_group("integration target arguments")
    int_group.add_argument(
        "--host-int",
        type=str,
        default=None,
        help="Integration Confluence host (env: CONFLUENCE_INT_HOST).",
    )
    int_group.add_argument(
        "--token-int",
        type=str,
        default=None,
        help="Integration Confluence token (env: CONFLUENCE_INT_TOKEN).",
    )
    int_group.add_argument(
        "--username-int",
        type=str,
        default=None,
        help="Integration Confluence username (env: CONFLUENCE_INT_USERNAME).",
    )
    int_group.add_argument(
        "--password-int",
        type=str,
        default=None,
        help="Integration Confluence password (env: CONFLUENCE_INT_PASSWORD).",
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Post-parse: reject --page-id ──────────────────────────────────
    if getattr(args, "page_id", None):
        parser.error(
            "--page-id is not supported by gitfluence. "
            "Pages are managed by directory hierarchy. "
            "Use --parent-id to anchor pages under a specific parent."
        )

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
        cli_host=args.host,
        cli_token=args.token,
        cli_username=args.username,
        cli_password=args.password,
        cli_host_int=args.host_int,
        cli_token_int=args.token_int,
        cli_username_int=args.username_int,
        cli_password_int=args.password_int,
        cli_space=args.space,
        cli_insecure=args.insecure,
    )

    # ── Preface / postface markup ─────────────────────────────────────
    preface_markup = ""
    if not args.no_preface:
        if args.preface_markdown:
            preface_markup = mdfluence.document.parse_page(
                [render_template(args.preface_markdown, git_info)]
            ).body
        elif args.preface_file:
            preface_markup = mdfluence.document.parse_page(
                [
                    render_template(
                        args.preface_file.read_text(encoding="utf-8"), git_info
                    )
                ]
            ).body
        else:
            preface_ref = _PACKAGE_FILES.joinpath("preface.md.template")
            if preface_ref.is_file():
                preface_markup = mdfluence.document.parse_page(
                    [render_template(preface_ref.read_text(encoding="utf-8"), git_info)]
                ).body

    postface_markup = ""
    if not args.no_postface:
        if args.postface_markdown:
            postface_markup = mdfluence.document.parse_page(
                [render_template(args.postface_markdown, git_info)]
            ).body
        elif args.postface_file:
            postface_markup = mdfluence.document.parse_page(
                [
                    render_template(
                        args.postface_file.read_text(encoding="utf-8"), git_info
                    )
                ]
            ).body
        else:
            postface_ref = _PACKAGE_FILES.joinpath("postface.md.template")
            if postface_ref.is_file():
                postface_md = render_template(
                    postface_ref.read_text(encoding="utf-8"), git_info
                )
                postface_markup = mdfluence.document.parse_page([postface_md]).body

    # ── Run ───────────────────────────────────────────────────────────
    run_sync(ctx, preface_markup, postface_markup, args=args)


if __name__ == "__main__":
    main()
