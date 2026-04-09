"""Shared fixtures for sync2cf tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from sync2cf.config import Sync2CfSettings


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.skip(f"{name} not set — required for integration tests")
    return val


@pytest.fixture(scope="session")
def int_host() -> str:
    return _require_env("CONFLUENCE_INT_HOST")


@pytest.fixture(scope="session")
def int_token() -> str:
    return _require_env("CONFLUENCE_INT_TOKEN")


@pytest.fixture(scope="session")
def confluence_space() -> str:
    return _require_env("CONFLUENCE_SPACE")


@pytest.fixture(scope="session")
def settings(int_host, int_token, confluence_space) -> Sync2CfSettings:
    return Sync2CfSettings(
        confluence_prod_host=int_host,
        confluence_prod_token=SecretStr(int_token),
        confluence_int_host=int_host,
        confluence_int_token=SecretStr(int_token),
        confluence_space=confluence_space,
    )


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one markdown file and a dummy origin."""
    import git as gitmodule

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Test Page\n\nHello from sync2cf tests.\n")
    repo = gitmodule.Repo.init(repo_dir, initial_branch="main")
    repo.index.add(["README.md"])
    repo.index.commit("initial")
    repo.create_remote("origin", "https://github.com/example/test-repo.git")
    return repo_dir
