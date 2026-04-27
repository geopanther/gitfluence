#!/usr/bin/env bash
# Create a release branch from the current (already bumped) version,
# sync lockfile, commit, push, open PR, and watch CI checks.
#
# Usage: ./scripts/prepare-release.sh
#
# Prerequisites:
#   - bump-my-version bump has already been run (without --commit)
#   - Working directory is the repo root
#   - gh CLI is authenticated

set -euo pipefail

VERSION="$(bump-my-version show current_version)"
if [[ -z "$VERSION" ]]; then
    echo "ERROR: Could not determine current version" >&2
    exit 1
fi

# Detect if this is an RC version
if [[ "$VERSION" =~ -rc[0-9]+$ ]]; then
    BRANCH="chore/bump-${VERSION}"
    PR_TITLE="Bumping version to ${VERSION}"
    # Revert RC heading in CHANGELOG.md — keep only ## Unreleased
    python scripts/revert_changelog_rc.py || true
else
    BRANCH="chore/release-${VERSION}"
    PR_TITLE="Release ${VERSION}"
fi

echo "==> Preparing release for v${VERSION} on branch ${BRANCH}"

# Create branch
git checkout -b "${BRANCH}"

# Sync lockfile
UV_LOCKED=0 uv sync --all-groups

# Commit all bumped files + lockfile
git add -A
git commit -m "Bump version: ${VERSION}"

# Push and create PR
git push --set-upstream origin "${BRANCH}"
gh pr create --title "${PR_TITLE}" --body "${PR_TITLE}"

echo "==> Watching CI checks..."
gh pr checks --watch
echo "==> CI passed. Ready to merge."
