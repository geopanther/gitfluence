"""Unit tests for gitfluence.confluence — preprocessing and orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from gitfluence.config import GitfluenceContext
from gitfluence.confluence import (
    _build_path_map,
    _collect_pages,
    _ensure_branch_page,
    _ensure_integration_root,
    _preprocess_page,
    _validate_relative_links,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_ctx(
    *,
    prefix=None,
    space="TEST",
    dry_run=False,
    write_host="https://int.example.com/api",
    write_token="tok",
):
    ctx = MagicMock(spec=GitfluenceContext)
    ctx.prefix = prefix
    ctx.space = space
    ctx.dry_run = dry_run
    ctx.write_host = write_host
    ctx.write_token = SecretStr(write_token)
    ctx.repo_path = Path("/tmp")
    return ctx


def _make_page(title="Test", parent_title=None, parent_id=None, file_path=None):
    page = MagicMock()
    page.title = title
    page.parent_title = parent_title
    page.parent_id = parent_id
    page.file_path = file_path
    page.body = "<p>body</p>"
    page.attachments = []
    page.relative_links = []
    page.content_type = "page"
    page.space = None
    return page


# ── Tests ─────────────────────────────────────────────────────────────────


class TestPreprocessPage:
    def test_top_level_page_gets_homepage_parent(self):
        page = _make_page(parent_title=None, parent_id=None)
        ctx = _make_ctx()
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="12345"))
        _preprocess_page(page, ctx, "", "", space_info)
        assert page.parent_id == "12345"
        assert page.space == "TEST"

    def test_top_level_uses_branch_page(self):
        page = _make_page(parent_title=None, parent_id=None)
        ctx = _make_ctx(prefix="feat/x")
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        root = SimpleNamespace(id="99")
        branch_page = SimpleNamespace(id="200")
        _preprocess_page(
            page,
            ctx,
            "",
            "",
            space_info,
            integration_root=root,
            branch_page=branch_page,
        )
        assert page.parent_id == "200"

    def test_top_level_falls_back_to_int_root(self):
        page = _make_page(parent_title=None, parent_id=None)
        ctx = _make_ctx(prefix="feat/x")
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        root = SimpleNamespace(id="99")
        _preprocess_page(page, ctx, "", "", space_info, integration_root=root)
        assert page.parent_id == "99"

    def test_child_page_parent_title_unchanged(self):
        page = _make_page(parent_title="Parent", parent_id=None)
        ctx = _make_ctx(prefix="feat/x")
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        root = SimpleNamespace(id="99")
        branch_page = SimpleNamespace(id="200")
        _preprocess_page(
            page,
            ctx,
            "",
            "",
            space_info,
            integration_root=root,
            branch_page=branch_page,
        )
        assert page.parent_id is None
        assert page.parent_title == "Parent"

    def test_no_prefix_applied_to_title_when_branch_page_present(self):
        page = _make_page(title="README")
        ctx = _make_ctx(prefix="feat/x")
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        branch_page = SimpleNamespace(id="200")
        _preprocess_page(page, ctx, "", "", space_info, branch_page=branch_page)
        assert page.title == "README"

    def test_no_prefix_applied_to_parent_title(self):
        page = _make_page(title="Child", parent_title="Parent")
        ctx = _make_ctx(prefix="dev")
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        branch_page = SimpleNamespace(id="200")
        _preprocess_page(page, ctx, "", "", space_info, branch_page=branch_page)
        assert page.parent_title == "Parent"
        assert page.title == "Child"

    def test_no_prefix_on_prod(self):
        page = _make_page(title="README")
        ctx = _make_ctx(prefix=None)
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        _preprocess_page(page, ctx, "", "", space_info)
        assert page.title == "README"

    def test_top_level_falls_back_to_homepage_without_roots(self):
        page = _make_page(parent_title=None, parent_id=None)
        ctx = _make_ctx(prefix=None)
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="42"))
        _preprocess_page(page, ctx, "", "", space_info)
        assert page.parent_id == "42"

    def test_preface_prepended(self):
        page = _make_page()
        page.body = "<p>content</p>"
        ctx = _make_ctx()
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        _preprocess_page(page, ctx, "<p>preface</p>", "", space_info)
        assert page.body.startswith("<p>preface</p>")

    def test_postface_appended(self):
        page = _make_page()
        page.body = "<p>content</p>"
        ctx = _make_ctx()
        space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
        _preprocess_page(page, ctx, "", "<p>postface</p>", space_info)
        assert page.body.endswith("<p>postface</p>")


class TestBuildPathMap:
    def test_maps_file_paths(self, tmp_path):
        p1 = _make_page(file_path=tmp_path / "a.md")
        p2 = _make_page(file_path=tmp_path / "b.md")
        p3 = _make_page(file_path=None)  # directory page
        result = _build_path_map([p1, p2, p3])
        assert (tmp_path / "a.md").resolve() in result
        assert (tmp_path / "b.md").resolve() in result
        assert len(result) == 2


class TestValidateRelativeLinks:
    def test_valid_links_pass(self, tmp_path):
        target = tmp_path / "other.md"
        page = _make_page(file_path=tmp_path / "a.md")
        link = MagicMock()
        link.path = "other.md"
        page.relative_links = [link]
        path_map = {target.resolve(): None}
        # Should not raise
        _validate_relative_links([page], path_map)

    def test_invalid_links_raise(self, tmp_path):
        page = _make_page(file_path=tmp_path / "a.md")
        link = MagicMock()
        link.path = "nonexistent.md"
        page.relative_links = [link]
        with pytest.raises(SystemExit, match="Invalid relative links"):
            _validate_relative_links([page], {})


class TestCollectPages:
    def test_collect_from_dir_with_markdown(self, tmp_repo):
        pages = _collect_pages(tmp_repo)
        assert len(pages) >= 1
        titles = [p.title for p in pages]
        assert "Test Page" in titles or any("README" in t for t in titles)

    def test_collect_empty_dir(self, tmp_path):
        pages = _collect_pages(tmp_path)
        assert not pages


class TestEnsureIntegrationRoot:
    def test_creates_root_under_homepage(self):
        confluence = MagicMock()
        result_mock = MagicMock()
        result_mock.action.name = "created"
        result_mock.response.id = "42"

        with patch(
            "gitfluence.confluence.upsert_page", return_value=result_mock
        ) as mock_upsert:
            ctx = _make_ctx(prefix="feat/x")
            ctx.repo_path = Path("/tmp/my-repo")
            space_info = SimpleNamespace(homepage=SimpleNamespace(id="1"))
            result = _ensure_integration_root(confluence, space_info, ctx)
            assert result.id == "42"
            mock_upsert.assert_called_once()

    def test_root_title_is_repo_dirname(self):
        confluence = MagicMock()
        result_mock = MagicMock()
        result_mock.action.name = "existed"

        with patch(
            "gitfluence.confluence.upsert_page", return_value=result_mock
        ) as mock_upsert:
            ctx = _make_ctx(prefix="feat/x")
            ctx.repo_path = Path("/work/git/my-awesome-repo")
            space_info = SimpleNamespace(homepage=SimpleNamespace(id="5"))
            _ensure_integration_root(confluence, space_info, ctx)
            page_arg = mock_upsert.call_args.kwargs["page"]
            assert page_arg.title == "my-awesome-repo"
            assert page_arg.parent_id == "5"


class TestEnsureBranchPage:
    def test_creates_branch_page_under_int_root(self):
        confluence = MagicMock()
        result_mock = MagicMock()
        result_mock.action.name = "created"
        result_mock.response.id = "300"

        with patch(
            "gitfluence.confluence.upsert_page", return_value=result_mock
        ) as mock_upsert:
            ctx = _make_ctx(prefix="feat/x")
            integration_root = SimpleNamespace(id="99")
            result = _ensure_branch_page(confluence, integration_root, ctx)
            assert result.id == "300"
            mock_upsert.assert_called_once()
            page_arg = mock_upsert.call_args.kwargs["page"]
            assert page_arg.parent_id == "99"

    def test_branch_page_title_format(self):
        confluence = MagicMock()
        result_mock = MagicMock()
        result_mock.action.name = "created"

        with patch(
            "gitfluence.confluence.upsert_page", return_value=result_mock
        ) as mock_upsert:
            ctx = _make_ctx(prefix="feat/x")
            integration_root = SimpleNamespace(id="99")
            _ensure_branch_page(confluence, integration_root, ctx)
            page_arg = mock_upsert.call_args.kwargs["page"]
            assert page_arg.title == "Branch: feat/x"

    def test_branch_page_body_is_empty(self):
        confluence = MagicMock()
        result_mock = MagicMock()
        result_mock.action.name = "created"

        with patch(
            "gitfluence.confluence.upsert_page", return_value=result_mock
        ) as mock_upsert:
            ctx = _make_ctx(prefix="feat/x")
            integration_root = SimpleNamespace(id="99")
            _ensure_branch_page(confluence, integration_root, ctx)
            page_arg = mock_upsert.call_args.kwargs["page"]
            assert page_arg.body == ""
