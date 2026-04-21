# Releasing

This document describes how to release new versions of gitfluence.

## Overview

The project uses a two-stage release pipeline:

1. **Release candidate** → published to [TestPyPI](https://test.pypi.org/project/gitfluence/) for validation (with approval gate)
2. **Final release** → published to [PyPI](https://pypi.org/project/gitfluence/) (with approval gate)

All publishing uses [PyPI Trusted Publishers (OIDC)](https://docs.pypi.org/trusted-publishers/) — no API tokens are involved. Packages include [digital attestations](https://docs.pypi.org/attestations/) for provenance verification.

## Prerequisites

- Write access to the repository
- For RC releases: approval rights on the `pypi-publish-test` GitHub environment
- For production releases: approval rights on the `pypi-publish-prod` GitHub environment
- Local dev environment set up (see [CONTRIBUTING.md](../CONTRIBUTING.md))

## Version format

Versions follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH` with optional `-rcN` suffix for release candidates.

Version bumping is managed by [bump2version](https://github.com/c4urself/bump2version) via `.bumpversion.cfg`. It updates `pyproject.toml`, `gitfluence/__init__.py`, and `CHANGELOG.md` automatically.

## Release candidate

Use this to test a release on TestPyPI before publishing to production.

### 1. Create a branch and bump to rc version

```bash
git checkout -b chore/bump-X.Y.Z-rc1
bump2version --new-version X.Y.Z-rc1 patch
```

This replaces the `## Unreleased` heading in `CHANGELOG.md` with the rc version and date. A pre-commit hook (`revert_changelog_rc.py`) will revert it back to `## Unreleased` on commit, so the changelog stays clean.

### 2. Commit and merge

```bash
git add -A
git commit -m "chore: bump version to X.Y.Z-rc1"
```

The first commit will fail because the `revert-changelog-rc` pre-commit hook reverts the rc heading back to `## Unreleased` and exits with code 1. This is expected — just re-run the commit:

```bash
git add -A && git commit -m "chore: bump version to X.Y.Z-rc1"
```

Push the branch, open a PR, and wait for CI checks (`lint` and `test`) to pass before merging to `main`.

### 3. Tag and push

```bash
git checkout main && git pull
git tag vX.Y.Z-rc1
git push origin vX.Y.Z-rc1
```

This triggers `deploy-test.yml`: **build → publish to TestPyPI**.

### 4. Approve the TestPyPI publish

Go to the Actions tab, find the running workflow, and approve the `publish-testpypi` job when prompted by the `pypi-publish-test` environment gate. Wait for the publish job to complete successfully before proceeding.

### 5. Verify on TestPyPI

Check the package page at `https://test.pypi.org/project/gitfluence/X.Y.Z-rc1/` and confirm:

- The package is listed
- Attestations are present (visible under "Provenance")

To test installation:

```bash
pip install -i https://test.pypi.org/simple/ gitfluence==X.Y.Z-rc1
```

### 6. Iterate if needed

For additional release candidates, bump the build number:

```bash
bump2version build
```

This increments `rc1` → `rc2`, etc. Commit, merge, tag, and push as above.

## Final release

### 1. Create a branch and bump to final version

```bash
git checkout -b chore/release-X.Y.Z
bump2version release
```

This removes the `-rcN` suffix, producing the final version `X.Y.Z`.

### 2. Update the changelog

The `## Unreleased` heading was replaced by the rc bump earlier and restored by the pre-commit hook. Now `bump2version release` replaces it with the final version and date heading. Review `CHANGELOG.md` to ensure all changes for this release are captured.

### 3. Commit and merge

```bash
git add -A
git commit -m "chore: release X.Y.Z"
```

Push the branch, open a PR, and wait for CI checks (`lint` and `test`) to pass before merging to `main`.

### 4. Tag and push

```bash
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

This triggers `deploy-prod.yml`: **build → GitHub Release → PyPI**.

The GitHub Release is created automatically with notes extracted from `CHANGELOG.md`. The `pypi-publish-prod` environment requires manual approval before publishing to PyPI.

### 5. Approve the production publish

Go to the Actions tab, find the running workflow, and approve the `publish-pypi` job when prompted. Wait for the publish job to complete successfully before proceeding.

## Workflows

| Workflow          | Trigger               | Pipeline               | Environment         |
| ----------------- | --------------------- | ---------------------- | ------------------- |
| `deploy-test.yml` | Any `v*` tag          | build → TestPyPI       | `pypi-publish-test` |
| `deploy-prod.yml` | `vX.Y.Z` tags (no rc) | build → release → PyPI | `pypi-publish-prod` |

## Security

- All GitHub Actions are pinned to full commit SHAs (not tags)
- Build and publish run in separate jobs — publish jobs never have access to source code or build tools
- OIDC authentication means no long-lived secrets exist
- Digital attestations provide cryptographic proof linking each package to this repository
- Both `pypi-publish-test` and `pypi-publish-prod` environments require reviewer approval
