"""Confluence sync orchestration using md2cf library API."""

from __future__ import annotations

import logging
from pathlib import Path

import md2cf.document
from md2cf.anchor import rewrite_page_anchors
from md2cf.api import MinimalConfluence
from md2cf.document import Page
from md2cf.upsert import upsert_attachment, upsert_page

from sync2cf.config import Sync2CfContext

log = logging.getLogger(__name__)


# ── Read/Write routing ────────────────────────────────────────────────────


class ReadWriteConfluence(MinimalConfluence):
    """Routes read operations to an optional read-only Confluence instance.

    Write operations always go through the primary (write) host.
    If no read host is configured, everything goes through the write host.
    """

    def __init__(self, ctx: Sync2CfContext) -> None:
        super().__init__(
            host=ctx.write_host,
            token=ctx.write_token.get_secret_value(),
        )
        if ctx.read_host and ctx.read_token:
            self._reader = MinimalConfluence(
                host=ctx.read_host,
                token=ctx.read_token.get_secret_value(),
            )
        else:
            self._reader = self  # type: ignore[assignment]

    # Override read-only methods to use the reader instance
    def get_page(self, *args, **kwargs):
        if self._reader is not self:
            return self._reader.get_page(*args, **kwargs)
        return super().get_page(*args, **kwargs)

    def get_space(self, *args, **kwargs):
        if self._reader is not self:
            return self._reader.get_space(*args, **kwargs)
        return super().get_space(*args, **kwargs)

    def get_attachment(self, *args, **kwargs):
        if self._reader is not self:
            return self._reader.get_attachment(*args, **kwargs)
        return super().get_attachment(*args, **kwargs)


# ── Main orchestration ────────────────────────────────────────────────────


def run_sync(ctx: Sync2CfContext, preface_markup: str, postface_markup: str) -> None:
    """Run the full sync: collect pages, preprocess, upsert, resolve links."""

    confluence = ReadWriteConfluence(ctx)

    # ── 1. Collect pages from directory ────────────────────────────────
    pages = _collect_pages(ctx.repo_path)
    if not pages:
        log.warning("No markdown pages found in %s", ctx.repo_path)
        return

    log.info("Collected %d page(s) from %s", len(pages), ctx.repo_path)

    # ── 2. Build relative-link map (filled in during upsert) ──────────
    path_to_page: dict[Path, Page | None] = _build_path_map(pages)
    _validate_relative_links(pages, path_to_page)

    # ── 3. Fetch space info for --top-level ───────────────────────────
    space_info = confluence.get_space(ctx.space, additional_expansions=["homepage"])

    # ── 4. Pre-process & upsert each page ─────────────────────────────
    something_went_wrong = False
    for page in pages:
        _preprocess_page(page, ctx, preface_markup, postface_markup, space_info)

        if ctx.dry_run:
            log.info("[dry-run] Would upsert: %s", page.title)
            continue

        try:
            result = upsert_page(
                confluence=confluence,
                message=None,
                page=page,
                only_changed=True,
                replace_all_labels=False,
                minor_edit=False,
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

        except Exception:
            log.exception("Failed to upsert page '%s'", page.title)
            something_went_wrong = True
            break

    # ── 5. Second pass: resolve relative links ────────────────────────
    if not something_went_wrong and not ctx.dry_run:
        _resolve_relative_links(confluence, pages, path_to_page, ctx)

    if something_went_wrong:
        raise SystemExit("ERROR: One or more pages failed to sync.")


# ── Internal helpers ──────────────────────────────────────────────────────


def _collect_pages(repo_path: Path) -> list[Page]:
    return list(
        md2cf.document.get_pages_from_directory(
            repo_path,
            collapse_single_pages=True,
            skip_empty=True,
            collapse_empty=False,
            beautify_folders=False,
            remove_text_newlines=False,
            strip_header=True,
            use_pages_file=False,
            use_gitignore=True,
            enable_relative_links=True,
            skip_subtrees_wo_markdown=True,
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


def _preprocess_page(
    page: Page,
    ctx: Sync2CfContext,
    preface_markup: str,
    postface_markup: str,
    space_info,
) -> None:
    page.original_title = page.title
    page.space = ctx.space
    page.content_type = "page"

    # Apply prefix to parent title (non-top-level pages)
    if page.parent_title is not None and ctx.prefix:
        page.parent_title = f"{ctx.prefix} - {page.parent_title}"

    # Top-level pages → child of space homepage
    if page.parent_title is None and page.parent_id is None:
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
    ctx: Sync2CfContext,
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
            except Exception:
                log.exception("Failed to update relative links for '%s'", page.title)
