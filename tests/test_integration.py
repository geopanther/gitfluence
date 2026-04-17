"""Integration tests that verify the full sync pipeline using a mock Confluence.

These tests exercise run_sync end-to-end — page collection, preprocessing,
upsert, and relative-link resolution — without hitting any real Confluence
instance.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import git as gitmodule
import pytest
from pydantic import SecretStr

from gitfluence.config import GitfluenceContext, GitfluenceSettings
from gitfluence.confluence import run_sync

from .mock_confluence import MockConfluence


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_confluence():
    """Fresh in-memory Confluence instance."""
    return MockConfluence(space_key="TEST", homepage_id=1)


@pytest.fixture()
def unique_prefix() -> str:
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


def _make_settings() -> GitfluenceSettings:
    return GitfluenceSettings(
        confluence_prod_host="http://mock.example.com/api",
        confluence_prod_token=SecretStr("mock-token"),
        confluence_space="TEST",
    )


def _run_sync_with_mock(
    mock_confluence: MockConfluence,
    test_repo: Path,
    *,
    prefix: str | None = None,
    dry_run: bool = False,
) -> GitfluenceContext:
    """Run sync against the mock, patching MinimalConfluence construction."""
    settings = _make_settings()
    ctx = GitfluenceContext(
        settings,
        repo_path=test_repo,
        use_prod=prefix is None,
        branch_name=prefix or "main",
        dry_run=dry_run,
    )

    with patch(
        "gitfluence.confluence.MinimalConfluence", return_value=mock_confluence
    ):
        run_sync(ctx, preface_markup="", postface_markup="")

    return ctx


# ── Tests ─────────────────────────────────────────────────────────────────


class TestFullSync:
    def test_pages_created(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        # Homepage + at least the 2 markdown pages
        assert len(mock_confluence.pages) >= 3

    def test_root_page_exists(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        page = mock_confluence.get_page_by_title(f"{unique_prefix} Root")
        assert page is not None, f"Root page '{unique_prefix} Root' not found"

    def test_sub_page_exists(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        page = mock_confluence.get_page_by_title(f"{unique_prefix} Sub")
        assert page is not None, f"Sub page '{unique_prefix} Sub' not found"

    def test_root_page_has_content(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        page = mock_confluence.get_page_by_title(f"{unique_prefix} Root")
        assert page is not None
        body = page.body.storage.value
        assert "Root page content" in body

    def test_pages_under_homepage(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        children = mock_confluence.get_children(parent_id=1)
        titles = [c.title for c in children]
        assert any(unique_prefix in t for t in titles), (
            f"No page with prefix '{unique_prefix}' under homepage. Children: {titles}"
        )

    def test_relative_links_resolved(self, mock_confluence, test_repo, unique_prefix):
        _run_sync_with_mock(mock_confluence, test_repo)

        root = mock_confluence.get_page_by_title(f"{unique_prefix} Root")
        assert root is not None
        body = root.body.storage.value
        # After link resolution, the body should contain mock.example.com URL
        assert "mock.example.com" in body


class TestIntegrationPrefix:
    def test_prefix_applied_to_titles(
        self, mock_confluence, test_repo, unique_prefix
    ):
        prefix = "feat/my-branch"
        _run_sync_with_mock(mock_confluence, test_repo, prefix=prefix)

        page = mock_confluence.get_page_by_title(
            f"{prefix} - {unique_prefix} Root"
        )
        assert page is not None, "Prefixed root page not found"

    def test_integration_root_created(
        self, mock_confluence, test_repo, unique_prefix
    ):
        prefix = "feat/my-branch"
        _run_sync_with_mock(mock_confluence, test_repo, prefix=prefix)

        # Integration root page is named after the repo directory
        repo_name = test_repo.name
        root = mock_confluence.get_page_by_title(repo_name)
        assert root is not None, f"Integration root '{repo_name}' not found"

    def test_prefixed_pages_under_int_root(
        self, mock_confluence, test_repo, unique_prefix
    ):
        prefix = "feat/my-branch"
        _run_sync_with_mock(mock_confluence, test_repo, prefix=prefix)

        repo_name = test_repo.name
        root = mock_confluence.get_page_by_title(repo_name)
        assert root is not None

        children = mock_confluence.get_children(root.id)
        titles = [c.title for c in children]
        assert any(prefix in t for t in titles), (
            f"No prefixed page under integration root. Children: {titles}"
        )


class TestPrefacePostface:
    def test_preface_prepended(self, mock_confluence, test_repo, unique_prefix):
        settings = _make_settings()
        ctx = GitfluenceContext(
            settings,
            repo_path=test_repo,
            use_prod=True,
            branch_name="main",
        )

        with patch(
            "gitfluence.confluence.MinimalConfluence",
            return_value=mock_confluence,
        ):
            run_sync(ctx, preface_markup="<p>PREFACE</p>", postface_markup="")

        root = mock_confluence.get_page_by_title(f"{unique_prefix} Root")
        assert root is not None
        assert root.body.storage.value.startswith("<p>PREFACE</p>")

    def test_postface_appended(self, mock_confluence, test_repo, unique_prefix):
        settings = _make_settings()
        ctx = GitfluenceContext(
            settings,
            repo_path=test_repo,
            use_prod=True,
            branch_name="main",
        )

        with patch(
            "gitfluence.confluence.MinimalConfluence",
            return_value=mock_confluence,
        ):
            run_sync(ctx, preface_markup="", postface_markup="<p>POSTFACE</p>")

        root = mock_confluence.get_page_by_title(f"{unique_prefix} Root")
        assert root is not None
        assert root.body.storage.value.endswith("<p>POSTFACE</p>")


class TestDryRun:
    def test_dry_run_creates_nothing(self, mock_confluence, test_repo):
        _run_sync_with_mock(mock_confluence, test_repo, dry_run=True)

        # Only the homepage should exist (pre-populated)
        assert len(mock_confluence.pages) == 1
