"""Shared fixtures for gitfluence tests.

When mdfluence is installed in editable mode from a source checkout,
its test suite (test_package/) is automatically collected alongside
gitfluence's own tests.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


log = logging.getLogger(__name__)


def pytest_collect_file(parent, file_path):
    """Collect mdfluence tests when available from an editable install."""
    # Only run once at the root session level
    return None


def pytest_configure(config):
    """Add mdfluence test_package to collection if available."""
    try:
        import mdfluence

        mdfluence_root = Path(mdfluence.__file__).resolve().parent.parent
        test_pkg = mdfluence_root / "test_package"
        if test_pkg.is_dir():
            # Add mdfluence repo root to sys.path so `from test_package.utils`
            # imports inside mdfluence tests resolve correctly.
            import sys

            mdfluence_root_str = str(mdfluence_root)
            if mdfluence_root_str not in sys.path:
                sys.path.insert(0, mdfluence_root_str)

            rootargs = config.args
            test_pkg_str = str(test_pkg)
            if test_pkg_str not in rootargs:
                rootargs.append(test_pkg_str)
                log.info("Collecting mdfluence tests from %s", test_pkg)
    except ImportError:
        pass


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one markdown file and a dummy origin."""
    import git as gitmodule  # pylint: disable=import-outside-toplevel

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Test Page\n\nHello from gitfluence tests.\n")
    repo = gitmodule.Repo.init(repo_dir, initial_branch="main")
    repo.index.add(["README.md"])
    repo.index.commit("initial")
    repo.create_remote("origin", "https://github.com/example/test-repo.git")
    return repo_dir
