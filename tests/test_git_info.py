"""Unit tests for gitfluence.git_info."""

# pylint: disable=duplicate-code

from __future__ import annotations

from pathlib import Path

import git as gitmodule

from gitfluence.git_info import GitInfo, get_git_info


class TestGitInfo:
    def test_use_prod_all_true(self):
        info = GitInfo(
            origin_url="git@github.com:org/repo.git",
            branch_name="main",
            default_branch="main",
            is_default_branch=True,
            is_clean=True,
            is_up_to_date=True,
        )
        assert info.use_prod is True

    def test_use_prod_dirty(self):
        info = GitInfo(
            origin_url="x",
            branch_name="main",
            default_branch="main",
            is_default_branch=True,
            is_clean=False,
            is_up_to_date=True,
        )
        assert info.use_prod is False

    def test_use_prod_wrong_branch(self):
        info = GitInfo(
            origin_url="x",
            branch_name="feat",
            default_branch="main",
            is_default_branch=False,
            is_clean=True,
            is_up_to_date=True,
        )
        assert info.use_prod is False

    def test_use_prod_behind_remote(self):
        info = GitInfo(
            origin_url="x",
            branch_name="main",
            default_branch="main",
            is_default_branch=True,
            is_clean=True,
            is_up_to_date=False,
        )
        assert info.use_prod is False


class TestGetGitInfo:
    def test_basic_repo(self, tmp_repo: Path):
        info = get_git_info(tmp_repo)
        assert info.branch_name in ("main", "master")
        assert info.is_clean is True
        # No remote tracking → not up to date
        assert info.is_up_to_date is False
        assert info.use_prod is False

    def test_dirty_repo(self, tmp_repo: Path):
        (tmp_repo / "new.txt").write_text("dirty")
        info = get_git_info(tmp_repo)
        assert info.is_clean is False

    def test_detached_head(self, tmp_repo: Path):
        repo = gitmodule.Repo(tmp_repo)
        repo.head.reference = repo.head.commit
        info = get_git_info(tmp_repo)
        # Should not crash; branch_name is a commit hash fragment
        assert len(info.branch_name) >= 7

    def test_detached_head_github_pr(self, tmp_repo, monkeypatch):
        repo = gitmodule.Repo(tmp_repo)
        repo.head.reference = repo.head.commit
        monkeypatch.setenv("GITHUB_HEAD_REF", "feature/my-pr")
        info = get_git_info(tmp_repo)
        assert info.branch_name == "feature/my-pr"

    def test_feature_branch(self, tmp_repo: Path):
        repo = gitmodule.Repo(tmp_repo)
        repo.create_head("feature/test").checkout()
        info = get_git_info(tmp_repo)
        assert info.branch_name == "feature/test"
        assert info.is_default_branch is False
