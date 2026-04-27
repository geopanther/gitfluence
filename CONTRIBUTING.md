# Contributing to gitfluence

gitfluence syncs markdown files from a git repository to Confluence. Built on top of [mdfluence](https://github.com/geopanther/mdfluence). Requires Python 3.12+.

## Prerequisites

The following tools must be installed on your system before setting up the project:

- [git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Setup

```bash
# Clone the repo
git clone https://github.com/geopanther/gitfluence.git
cd gitfluence

# Create a virtual environment
uv sync --python 3.12 --group dev

# Set up pre-commit hooks
uv run pre-commit install
```

<details open>
<summary><b>macOS / Linux</b></summary>

Copy `setenv.example.sh` to `setenv.sh` and fill in your values:

```bash
cp setenv.example.sh setenv.sh
```

Edit `setenv.sh` with your Confluence details.

```bash
source setenv.sh
```

</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

Follow the shared setup steps above (clone, `uv sync`, `uv run pre-commit install`), then configure environment variables:

Copy `setenv.example.ps1` to `setenv.ps1` and fill in your values:

```powershell
Copy-Item setenv.example.ps1 setenv.ps1
```

Edit setenv.ps1 with your Confluence details.

```powershell
. .\setenv.ps1
```

</details>

Sourcing `setenv.sh` (or dot-sourcing `setenv.ps1` on Windows) sets required environment variables and adds a `uv` wrapper that automatically runs `osv-scanner` (via pre-commit) after lockfile-changing commands (`uv lock`, `uv add`, `uv remove`, `uv sync`).

## Project structure

```
gitfluence/         # Package source
tests/              # Tests (unit + integration with mock Confluence)
pyproject.toml      # Build config, dependencies, tool settings
.bumpversion.cfg    # Version bump configuration
.github/workflows/  # CI (lint + test) and deploy (PyPI + GitHub Release)
```

## Linting

Linting runs automatically on `git-commit`, via [pre-commit](https://pre-commit.com/). To run manually:

```bash
uv run pre-commit run --all-files
```

## Type checking

[ty](https://github.com/astral-sh/ty) (Astral's type checker) runs as part of pre-commit. To run manually:

```bash
uv run ty check gitfluence
```

## Testing

Tests run against Python 3.12 and 3.13 via [tox](https://tox.wiki/):

```bash
# Run tests against all configured Python versions (requires local Python 3.13 installation)
uv run tox

# Run against a single version
uv run tox -e py312

# Run pytest directly (current venv only)
uv run pytest
```

Tests live in `tests/`. The test suite uses pytest, pytest-mock, pyfakefs, and requests-mock.

When mdfluence is installed in editable mode from a local clone, its own test suite is automatically collected and executed alongside gitfluence's tests. This ensures the underlying library API remains compatible.

## Building

Build the package using [uv](https://docs.astral.sh/uv/concepts/projects/build/):

```bash
uv build
```

This produces source and wheel distributions in `dist/`. To test install the built package locally:

```bash
uv pip install dist/gitfluence-*.whl
```

## Releasing

See [docs/releasing.md](docs/releasing.md) for the full release process, including version bumping, release candidates, and production publishing.
