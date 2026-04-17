"""Confluence sync orchestration using mdfluence library API."""

from __future__ import annotations

import logging
from pathlib import Path

import mdfluence.document
from mdfluence.anchor import rewrite_page_anchors
from mdfluence.api import MinimalConfluence
from mdfluence.document import Page
from mdfluence.upsert import upsert_attachment, upsert_page

from gitfluence.config import GitfluenceContext

log = logging.getLogger(__name__)


# ── Main orchestration ────────────────────────────────────────────────────


def run_sync(
    ctx: GitfluenceContext,
    preface_markup: str,
    postface_markup: str,
    *,
    args=None,
) -> None:
    """Run the full sync: collect pages, preprocess, upsert, resolve links."""

    # ── 1. Collect pages from directory ────────────────────────────────
    pages = _collect_pages(ctx.repo_path, args=args)
    if not pages:
        log.warning("No markdown pages found in %s", ctx.repo_path)
        return

    log.info("Collected %d page(s) from %s", len(pages), ctx.repo_path)

    # ── 2. Build relative-link map (filled in during upsert) ──────────
    path_to_page: dict[Path, Page | None] = _build_path_map(pages)
    _validate_relative_links(pages, path_to_page)

    # ── 3. Fetch space info for --top-level ───────────────────────────
    if ctx.dry_run:
        # In dry-run mode we skip Confluence API calls entirely
        for page in pages:
            _preprocess_page(page, ctx, preface_markup, postface_markup, None)
            log.info("[dry-run] Would upsert: %s", page.title)
        return

    confluence = MinimalConfluence(
        host=ctx.write_host,
        token=ctx.write_token.get_secret_value(),
        insecure=getattr(args, "insecure", False) if args else False,
        max_retries=getattr(args, "max_retries", 3) if args else 3,
    )
    space_info = confluence.get_space(ctx.space, additional_expansions=["homepage"])

    # ── 3b. Integration root page ─────────────────────────────────────
    integration_root = None
    if ctx.prefix:
        integration_root = _ensure_integration_root(
            confluence,
            space_info,
            ctx,
        )

    # ── 4. Pre-process & upsert each page ─────────────────────────────
    something_went_wrong = False
    for page in pages:
        _preprocess_page(
            page,
            ctx,
            preface_markup,
            postface_markup,
            space_info,
            integration_root=integration_root,
        )

        try:
            result = upsert_page(
                confluence=confluence,
                message=getattr(args, "message", None) if args else None,
                page=page,
                only_changed=getattr(args, "only_changed", True) if args else True,
                replace_all_labels=(
                    getattr(args, "replace_all_labels", False) if args else False
                ),
                minor_edit=getattr(args, "minor_edit", False) if args else False,
            )
            log.info("Upserted page '%s' (%s)", page.title, result.action.name)

            final_page = result.response

            # Upload attachments
            for attachment in page.attachments:
                upsert_attachment(
                    confluence=confluence,
                    attachment=attachment,
                    existing_page=final_page,
                    message=None,
                    only_changed=True,
                    page=page,
                )

            # Record for relative link resolution
            if page.file_path is not None:
                path_to_page[page.file_path.resolve()] = final_page

        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("Failed to upsert page '%s'", page.title)
            something_went_wrong = True
            break

    # ── 5. Second pass: resolve relative links ────────────────────────
    if not something_went_wrong and not ctx.dry_run:
        _resolve_relative_links(confluence, pages, path_to_page, ctx)

    if something_went_wrong:
        raise SystemExit("ERROR: One or more pages failed to sync.")


# ── Internal helpers ──────────────────────────────────────────────────────


def _collect_pages(repo_path: Path, *, args=None) -> list[Page]:
    return list(
        mdfluence.document.get_pages_from_directory(  # pylint: disable=no-member
            repo_path,
            collapse_single_pages=(
                getattr(args, "collapse_single_pages", True) if args else True
            ),
            skip_empty=getattr(args, "skip_empty", True) if args else True,
            collapse_empty=getattr(args, "collapse_empty", False) if args else False,
            beautify_folders=(
                getattr(args, "beautify_folders", False) if args else False
            ),
            remove_text_newlines=(
                getattr(args, "remove_text_newlines", False) if args else False
            ),
            strip_header=(getattr(args, "strip_top_header", True) if args else True),
            use_pages_file=(getattr(args, "use_pages_file", False) if args else False),
            use_gitignore=(not getattr(args, "no_gitignore", False) if args else True),
            enable_relative_links=(
                getattr(args, "enable_relative_links", True) if args else True
            ),
            skip_subtrees_wo_markdown=(
                getattr(args, "skip_subtrees_wo_markdown", True) if args else True
            ),
        )
    )


def _build_path_map(pages: list[Page]) -> dict[Path, Page | None]:
    path_map: dict[Path, Page | None] = {}
    for page in pages:
        if page.file_path is not None:
            path_map[page.file_path.resolve()] = None
    return path_map


def _validate_relative_links(
    pages: list[Page], path_map: dict[Path, Page | None]
) -> None:
    invalid = False
    for page in pages:
        for link in page.relative_links:
            abs_path = (page.file_path.parent / Path(link.path)).resolve()
            if abs_path not in path_map:
                log.error(
                    "Page %s has relative link to %s which is not in upload set",
                    page.file_path,
                    link.path,
                )
                invalid = True
    if invalid:
        raise SystemExit("ERROR: Invalid relative links detected.")


def _ensure_integration_root(
    confluence: MinimalConfluence,
    space_info,
    ctx: GitfluenceContext,
):
    """Upsert an empty root page named after the repo directory under the space homepage.

    All integration pages are created as children of this page so that
    deleting it (and its descendants) cleans up all integration artifacts.
    """
    root_page = Page(
        space=ctx.space,
        title=ctx.repo_path.name,
        body="",
        content_type="page",
    )
    root_page.parent_id = space_info.homepage.id

    result = upsert_page(
        confluence=confluence,
        message=None,
        page=root_page,
        only_changed=True,
        replace_all_labels=False,
        minor_edit=True,
    )
    log.info(
        "Integration root page '%s' (%s)",
        root_page.title,
        result.action.name,
    )
    return result.response


def _preprocess_page(
    page: Page,
    ctx: GitfluenceContext,
    preface_markup: str,
    postface_markup: str,
    space_info,
    *,
    integration_root=None,
) -> None:
    page.original_title = page.title
    page.space = ctx.space
    page.content_type = "page"

    # Apply prefix to parent title (non-top-level pages)
    if page.parent_title is not None and ctx.prefix:
        page.parent_title = f"{ctx.prefix} - {page.parent_title}"

    # Top-level pages → child of integration root (int) or space homepage (prod)
    if page.parent_title is None and page.parent_id is None:
        if integration_root is not None:
            page.parent_id = integration_root.id
        elif space_info is not None:
            page.parent_id = space_info.homepage.id

    # Apply prefix to page title
    if ctx.prefix:
        page.title = f"{ctx.prefix} - {page.title}"

    # Preface / postface
    if preface_markup:
        page.body = preface_markup + page.body
    if postface_markup:
        page.body = page.body + postface_markup

    # Anchor conversion
    page.body = rewrite_page_anchors(page.body, page.title)


def _resolve_relative_links(
    confluence: MinimalConfluence,
    pages: list[Page],
    path_to_page: dict[Path, Page | None],
    ctx: GitfluenceContext,  # pylint: disable=unused-argument
) -> None:
    for page in pages:
        if page.file_path is None:
            continue

        modified = False
        for link in page.relative_links:
            abs_path = (page.file_path.parent / Path(link.path)).resolve()
            target = path_to_page.get(abs_path)
            if target is None:
                # Restore original link text
                page.body = page.body.replace(
                    link.replacement,
                    link.escaped_original
                    + (("#" + link.fragment) if link.fragment else ""),
                )
                continue

            url = confluence.get_url(target)
            page.body = page.body.replace(
                link.replacement,
                url + (("#" + link.fragment) if link.fragment else ""),
            )
            modified = True

        if modified:
            try:
                upsert_page(
                    confluence=confluence,
                    message=None,
                    page=page,
                    only_changed=True,
                    replace_all_labels=False,
                    minor_edit=True,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to update relative links for '%s'", page.title)
