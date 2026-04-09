"""Integration tests that verify pages on Confluence INT via atlassian-python-api.

These tests require CONFLUENCE_INT_HOST, CONFLUENCE_INT_TOKEN, and
CONFLUENCE_SPACE to be set.  They create test pages, verify them via the
Atlassian REST client, and clean up afterwards.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import git as gitmodule
import pytest
from atlassian import Confluence

pytestmark = pytest.mark.integration

from sync2cf.config import Sync2CfContext  # noqa: E402
from sync2cf.confluence import run_sync  # noqa: E402


@pytest.fixture(scope="session")
def atlassian_client(int_host, int_token) -> Confluence:
    """Atlassian Confluence client pointing at INT for verification."""
    # atlassian-python-api expects the base URL without /rest/api
    base_url = int_host.replace("/rest/api", "")
    return Confluence(url=base_url, token=int_token)


@pytest.fixture()
def unique_prefix() -> str:
    """Short unique prefix to isolate test pages."""
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def test_repo(tmp_path: Path, unique_prefix: str) -> Path:
    """Minimal git repo with two linked markdown files."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    (repo_dir / "README.md").write_text(
        f"# {unique_prefix} Root\n\nRoot page content.\n\nSee [sub](doc/sub.md).\n"
    )
    doc_dir = repo_dir / "doc"
    doc_dir.mkdir()
    (doc_dir / "sub.md").write_text(f"# {unique_prefix} Sub\n\nSub page content.\n")

    repo = gitmodule.Repo.init(repo_dir)
    repo.index.add(["README.md", "doc/sub.md"])
    repo.index.commit("initial")
    return repo_dir


@pytest.fixture()
def synced_pages(
    test_repo, settings, unique_prefix, confluence_space, atlassian_client
):
    """Run sync and yield prefix; clean up pages afterwards."""
    ctx = Sync2CfContext(
        settings,
        repo_path=test_repo,
        use_prod=False,
        branch_name=unique_prefix,
        dry_run=False,
    )
    run_sync(ctx, preface_markup="", postface_markup="")

    yield unique_prefix

    # ── Cleanup: delete test pages (children first) ───────────────────
    for title_suffix in ["Sub", "Root", "doc", "repo"]:
        title = f"{unique_prefix} - {title_suffix}"
        try:
            page = atlassian_client.get_page_by_title(
                space=confluence_space, title=title
            )
            if page:
                atlassian_client.remove_page(page["id"], recursive=True)
        except Exception:
            pass
    # Also try prefixed versions of folder pages
    for title in [
        f"{unique_prefix} - {unique_prefix} Root",
        f"{unique_prefix} - {unique_prefix} Sub",
    ]:
        try:
            page = atlassian_client.get_page_by_title(
                space=confluence_space, title=title
            )
            if page:
                atlassian_client.remove_page(page["id"], recursive=True)
        except Exception:
            pass


class TestIntegrationSync:
    """Tests that run a real sync against Confluence INT and verify results."""

    def test_root_page_created(self, synced_pages, atlassian_client, confluence_space):
        prefix = synced_pages
        page = atlassian_client.get_page_by_title(
            space=confluence_space,
            title=f"{prefix} - {prefix} Root",
        )
        assert page is not None, f"Root page '{prefix} - {prefix} Root' not found"
        assert page["title"] == f"{prefix} - {prefix} Root"

    def test_sub_page_created(self, synced_pages, atlassian_client, confluence_space):
        prefix = synced_pages
        page = atlassian_client.get_page_by_title(
            space=confluence_space,
            title=f"{prefix} - {prefix} Sub",
        )
        assert page is not None, f"Sub page '{prefix} - {prefix} Sub' not found"

    def test_root_page_has_content(
        self, synced_pages, atlassian_client, confluence_space
    ):
        prefix = synced_pages
        page = atlassian_client.get_page_by_title(
            space=confluence_space,
            title=f"{prefix} - {prefix} Root",
            expand="body.storage",
        )
        assert page is not None
        body = page["body"]["storage"]["value"]
        assert "Root page content" in body

    def test_page_is_child_of_homepage(
        self, synced_pages, atlassian_client, confluence_space
    ):
        prefix = synced_pages
        space_info = atlassian_client.get_space(confluence_space, expand="homepage")
        homepage_id = space_info["homepage"]["id"]

        # Find our root-level page(s) — they should be children of homepage
        children = atlassian_client.get_page_child_by_type(
            homepage_id, type="page", limit=200
        )
        child_titles = [c["title"] for c in children]
        # At least one of our test pages should be a direct child
        found = any(prefix in t for t in child_titles)
        assert found, (
            f"No test page with prefix '{prefix}' found as child of homepage. "
            f"Children: {child_titles[:10]}"
        )

    def test_dry_run_creates_nothing(
        self, test_repo, settings, atlassian_client, confluence_space
    ):
        dry_prefix = f"dry-{uuid.uuid4().hex[:8]}"
        ctx = Sync2CfContext(
            settings,
            repo_path=test_repo,
            use_prod=False,
            branch_name=dry_prefix,
            dry_run=True,
        )
        run_sync(ctx, preface_markup="", postface_markup="")

        page = atlassian_client.get_page_by_title(
            space=confluence_space,
            title=f"{dry_prefix} - {dry_prefix} Root",
        )
        assert page is None, "Dry run should not create pages"
