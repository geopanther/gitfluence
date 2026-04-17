# Contributing to gitfluence

gitfluence syncs markdown files from a git repository to Confluence. Built on top of [mdfluence](https://github.com/geopanther/mdfluence). Requires Python 3.12+.

## Setup

```bash
# Clone the repo
git clone https://github.com/geopanther/gitfluence.git
cd gitfluence

# Create a virtual environment
python3.12 -m venv .venv --prompt gitfluence
source .venv/bin/activate

# Install the package with dev and test dependencies
pip install -e ".[dev,test]"

# Set up pre-commit hooks
pre-commit install
```

## Testing

Tests run against Python 3.12 and 3.13 via [tox](https://tox.wiki/):

```bash
# Run tests against all configured Python versions (requires local Python 3.13 installation)
tox

# Run against a single version
tox -e py312

# Run pytest directly (current venv only)
pytest
```

Tests live in `tests/`. The test suite uses pytest, pytest-mock, pyfakefs, and requests-mock.

When mdfluence is installed in editable mode from a local clone, its own test suite is automatically collected and executed alongside gitfluence's tests. This ensures the underlying library API remains compatible.

## Linting

Linting runs automatically on `git push` via [pre-commit](https://pre-commit.com/) (configured with `pre-push` stage). To run manually:

```bash
pre-commit run --all-files
```

## Releasing

See [docs/releasing.md](docs/releasing.md) for the full release process, including version bumping, release candidates, and production publishing.

## Project structure

```
gitfluence/         # Package source
tests/              # Tests (unit + integration with mock Confluence)
pyproject.toml      # Build config, dependencies, tool settings
.bumpversion.cfg    # Version bump configuration
.github/workflows/  # CI (lint + test) and deploy (PyPI + GitHub Release)
```
