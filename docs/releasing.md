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
- On up-to-date main branch without local changes.

## Version format

Versions follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH` with optional `-rcN` suffix for release candidates.

Version bumping is managed by [bump-my-version](https://github.com/callowayproject/bump-my-version) via `.bumpversion.toml`. It updates `pyproject.toml`, `gitfluence/__init__.py`, and `CHANGELOG.md` automatically.

Two helper scripts handle the git workflow after bumping:

- `scripts/prepare-release.sh` — creates branch, syncs lockfile, commits, pushes, opens PR, watches CI
- `scripts/commit-release.sh` — checks out main, tags the release, pushes tag to trigger deployment

## Preparation

To avoid having to prepend all commands with `uv run`, simply activate the current environment.

```bash
. .venv/bin/activate
```

Ensure that your local `.venv` is in sync.

```bash
uv sync --locked --all-groups
```

## Release candidate

Use this to test a release on TestPyPI before publishing to production.

### 1. Bump version

From the up-to-date `main` branch, bump to the desired RC version:

```bash
bump-my-version bump minor   # 0.1.0 → 0.2.0-rc0
```

For subsequent release candidates:

```bash
bump-my-version bump pre_n   # rc0 → rc1, rc1 → rc2, etc.
```

To jump to a specific version (e.g. new minor):

```bash
bump-my-version bump minor   # 0.1.0 → 0.2.0-rc0
bump-my-version bump pre_n   # 0.2.0-rc0 → 0.2.0-rc1
```

Verify the result:

```bash
bump-my-version show current_version
```

### 2. Prepare and merge

```bash
./scripts/prepare-release.sh
```

This creates a branch, syncs the lockfile, commits, pushes, opens a PR, and watches CI.
For RC versions, it also removes the RC heading from `CHANGELOG.md` (keeping only `## Unreleased`).

Once CI passes, merge:

```bash
gh pr merge --merge
```

### 3. Tag and push

```bash
./scripts/commit-release.sh
```

This checks out `main`, tags `v<version>`, and pushes. Triggers `deploy-test.yml`: **build → publish to TestPyPI**.

### 4. Approve the TestPyPI publish

Go to the Actions tab, find the running workflow, and approve the `publish-testpypi` job when prompted by the `pypi-publish-test` environment gate. Wait for the publish job to complete successfully before proceeding.

### 5. Verify on TestPyPI

Check the package page at `https://test.pypi.org/project/gitfluence/<VERSION>/` and confirm:

- The package is listed
- Attestations are present (visible under "Provenance")

To test installation:

```bash
uv pip install -i https://test.pypi.org/simple/ gitfluence==<VERSION>
```

### 6. Iterate if needed

Repeat steps 1–5 using `bump-my-version bump pre_n` to increment the RC number.

## Final release

### 1. Bump version

From the up-to-date `main` branch, bump to the final version:

```bash
bump-my-version bump pre_l   # e.g. 0.2.0-rc1 → 0.2.0
```

Verify:

```bash
bump-my-version show current_version
```

### 2. Prepare and merge

```bash
./scripts/prepare-release.sh
```

Once CI passes, merge:

```bash
gh pr merge --merge
```

### 3. Tag and push

```bash
./scripts/commit-release.sh
```

This triggers `deploy-prod.yml`: **build → GitHub Release → PyPI**.

The GitHub Release is created automatically with notes extracted from `CHANGELOG.md`. The `pypi-publish-prod` environment requires manual approval before publishing to PyPI.

### 4. Approve the production publish

Go to the Actions tab, find the running workflow, and approve the `publish-pypi` job when prompted by the `pypi-publish-prod` environment gate. Wait for the publish job to complete successfully before proceeding.

### 5. Verify on PyPI

Check the package page at `https://pypi.org/project/gitfluence/<VERSION>/` and confirm:

- The package is listed
- Attestations are present (visible under "Provenance")

To test installation:

```bash
uv pip install gitfluence==<VERSION>
```

## Workflows

| Workflow          | Trigger                              | Pipeline               | Environment         |
| ----------------- | ------------------------------------ | ---------------------- | ------------------- |
| `deploy-test.yml` | Any `v*` tag                         | build → TestPyPI       | `pypi-publish-test` |
| `deploy-prod.yml` | `v${NEW_VERSION_FINAL}` tags (no rc) | build → release → PyPI | `pypi-publish-prod` |

## Security

- All GitHub Actions are pinned to full commit SHAs (not tags)
- Build and publish run in separate jobs — publish jobs never have access to source code or build tools
- OIDC authentication means no long-lived secrets exist
- Digital attestations provide cryptographic proof linking each package to this repository
- Both `pypi-publish-test` and `pypi-publish-prod` environments require reviewer approval
