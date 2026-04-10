"""Detect git branch, remote state and working-tree cleanliness."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import git

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitInfo:
    origin_url: str
    branch_name: str
    default_branch: str
    is_default_branch: bool
    is_clean: bool
    is_up_to_date: bool

    @property
    def use_prod(self) -> bool:
        """Use production Confluence when on unmodified, up-to-date default branch."""
        return self.is_default_branch and self.is_clean and self.is_up_to_date


def get_git_info(repo_path: Path) -> GitInfo:
    """Inspect the working tree at *repo_path* and return a `GitInfo`."""
    repo = git.Repo(repo_path)

    # ── origin URL ─────────────────────────────────────────────────────
    origin_url = repo.remotes.origin.url if repo.remotes else "unknown"

    # ── current branch ─────────────────────────────────────────────────
    try:
        branch_name = repo.active_branch.name
    except TypeError:
        # detached HEAD
        branch_name = str(repo.head.commit)[:12]

    # ── default branch (from origin/HEAD or fallback) ──────────────────
    default_branch = _detect_default_branch(repo)

    # ── cleanliness ────────────────────────────────────────────────────
    is_clean = not repo.is_dirty(untracked_files=True)

    # ── up-to-date with remote tracking branch ─────────────────────────
    is_up_to_date = _check_up_to_date(repo, branch_name)

    info = GitInfo(
        origin_url=origin_url,
        branch_name=branch_name,
        default_branch=default_branch,
        is_default_branch=(branch_name == default_branch),
        is_clean=is_clean,
        is_up_to_date=is_up_to_date,
    )
    log.info("Git info: %s", info)
    return info


def _detect_default_branch(repo: git.Repo) -> str:
    """Return the default branch name, guessed from origin/HEAD."""
    try:
        ref = repo.remotes.origin.refs["HEAD"]
        # ref.reference is something like origin/main
        return ref.reference.remote_head
    except (IndexError, KeyError, TypeError, AttributeError):
        pass
    # Fallback: try common names
    for name in ("main", "master"):
        if name in [r.remote_head for r in repo.remotes.origin.refs]:
            return name
    return "main"


def _check_up_to_date(  # pylint: disable=unused-argument
    repo: git.Repo, branch_name: str
) -> bool:
    """Return True if the local branch HEAD matches its remote tracking branch."""
    try:
        tracking = repo.active_branch.tracking_branch()
        if tracking is None:
            return False
        # Fetch latest info is NOT done here — we trust local refs as-is.
        return repo.head.commit == tracking.commit
    except (TypeError, ValueError):
        return False
