"""Test bump-my-version lifecycle: version chain, file updates, changelog behavior."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimal CHANGELOG template matching real repo structure
CHANGELOG_TEMPLATE = """\
# Changelog

## Unreleased

### Added

- Something new
"""

# Minimal pyproject.toml — only needs [project] with version
PYPROJECT_TEMPLATE = """\
[project]
name = "gitfluence"
version = "{version}"
"""

INIT_TEMPLATE = '__version__ = "{version}"\n'


def _run(cmd: str, cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def bump_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with bumpversion config starting at 0.1.0."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Copy real bumpversion config and reset current_version to test starting point
    config_text = (REPO_ROOT / ".bumpversion.toml").read_text()
    config_text = re.sub(
        r'^current_version = ".*"',
        'current_version = "0.1.0"',
        config_text,
        count=1,
        flags=re.MULTILINE,
    )
    (repo / ".bumpversion.toml").write_text(config_text)

    # Create minimal target files
    pkg = repo / "gitfluence"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(INIT_TEMPLATE.format(version="0.1.0"))
    (repo / "pyproject.toml").write_text(PYPROJECT_TEMPLATE.format(version="0.1.0"))
    (repo / "CHANGELOG.md").write_text(CHANGELOG_TEMPLATE)

    # Init git repo (bumpversion requires it for allow_dirty=false)
    _run("git init", repo)
    _run("git add -A", repo)
    _run("git commit -m 'init'", repo)

    return repo


def _get_version(repo: Path) -> str:
    return _run("bump-my-version show current_version", repo)


def _bump(repo: Path, part: str) -> str:
    _run(f"bump-my-version bump {part} --allow-dirty", repo)
    return _get_version(repo)


def _read_version_from_init(repo: Path) -> str:
    text = (repo / "gitfluence" / "__init__.py").read_text()
    # Extract version from __version__ = "..."
    return text.split('"')[1]


def _read_version_from_pyproject(repo: Path) -> str:
    for line in (repo / "pyproject.toml").read_text().splitlines():
        if line.startswith("version"):
            return line.split('"')[1]
    raise ValueError("No version found in pyproject.toml")


def _assert_version_consistent(repo: Path, expected: str) -> None:
    """Assert all version sources agree."""
    assert _get_version(repo) == expected
    assert _read_version_from_init(repo) == expected
    assert _read_version_from_pyproject(repo) == expected


def _changelog_text(repo: Path) -> str:
    return (repo / "CHANGELOG.md").read_text()


class TestVersionLifecycle:
    """Walk through a full release lifecycle and verify each step."""

    def test_minor_rc_release_cycle(self, bump_repo: Path) -> None:
        """0.1.0 → 0.2.0-rc0 → 0.2.0-rc1 → 0.2.0"""
        repo = bump_repo
        _assert_version_consistent(repo, "0.1.0")

        # First RC
        _bump(repo, "minor")
        _assert_version_consistent(repo, "0.2.0-rc0")

        # Second RC
        _bump(repo, "pre_n")
        _assert_version_consistent(repo, "0.2.0-rc1")

        # Final release
        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.2.0")

    def test_patch_rc_release_cycle(self, bump_repo: Path) -> None:
        """0.1.0 → 0.1.1-rc0 → 0.1.1"""
        repo = bump_repo
        _bump(repo, "patch")
        _assert_version_consistent(repo, "0.1.1-rc0")

        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.1.1")

    def test_major_rc_release_cycle(self, bump_repo: Path) -> None:
        """0.1.0 → 1.0.0-rc0 → 1.0.0"""
        repo = bump_repo
        _bump(repo, "major")
        _assert_version_consistent(repo, "1.0.0-rc0")

        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "1.0.0")

    def test_consecutive_releases(self, bump_repo: Path) -> None:
        """0.1.0 → 0.2.0-rc0 → 0.2.0 → 0.3.0-rc0 → 0.3.0"""
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.2.0")

        _bump(repo, "minor")
        _assert_version_consistent(repo, "0.3.0-rc0")

        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.3.0")

    def test_patch_after_minor(self, bump_repo: Path) -> None:
        """0.1.0 → 0.2.0-rc0 → 0.2.0 → 0.2.1-rc0 → 0.2.1"""
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.2.0")

        _bump(repo, "patch")
        _assert_version_consistent(repo, "0.2.1-rc0")

        _bump(repo, "pre_l")
        _assert_version_consistent(repo, "0.2.1")


class TestChangelogBehavior:
    """Verify CHANGELOG.md heading insertion."""

    def test_bump_adds_version_heading(self, bump_repo: Path) -> None:
        """Bump should insert version heading below ## Unreleased."""
        repo = bump_repo
        _bump(repo, "minor")
        text = _changelog_text(repo)
        assert "## Unreleased" in text
        assert "## [0.2.0-rc0]" in text

    def test_unreleased_preserved_after_multiple_bumps(self, bump_repo: Path) -> None:
        """## Unreleased must survive all bumps."""
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_n")
        _bump(repo, "pre_l")
        text = _changelog_text(repo)
        assert "## Unreleased" in text
        assert "## [0.2.0]" in text

    def test_rc_headings_accumulate(self, bump_repo: Path) -> None:
        """Each RC bump adds another heading (revert script cleans them)."""
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_n")
        text = _changelog_text(repo)
        assert "## [0.2.0-rc0]" in text
        assert "## [0.2.0-rc1]" in text


class TestRevertChangelogRc:
    """Test scripts/revert_changelog_rc.py removes RC headings."""

    def test_removes_rc_headings(self, bump_repo: Path) -> None:
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_n")

        # Copy revert script and run it
        shutil.copy(REPO_ROOT / "scripts" / "revert_changelog_rc.py", repo)
        _run("python revert_changelog_rc.py", repo)

        text = _changelog_text(repo)
        assert "## Unreleased" in text
        assert "rc" not in text.lower().split("unreleased")[1]

    def test_noop_on_final_version(self, bump_repo: Path) -> None:
        """Revert script should not touch final version headings."""
        repo = bump_repo
        _bump(repo, "minor")
        _bump(repo, "pre_l")

        shutil.copy(REPO_ROOT / "scripts" / "revert_changelog_rc.py", repo)
        _run("python revert_changelog_rc.py", repo)

        text = _changelog_text(repo)
        assert "## [0.2.0]" in text
