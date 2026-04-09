# sync2cf

Sync markdown files from any GitHub repo working tree to Confluence as a page hierarchy.

Uses [md2cf](https://github.com/geopanther/md2cf) (pre-integration branch) for markdown → Confluence conversion and upload. Pages are created as **children of the space's home page** (md2cf's `--top-level` behavior) — the space itself is never overwritten.

This repo's own workflow (`.github/workflows/sync2cf.yml`) syncs its own README to Confluence as a working example.

## Usage

```bash
python -m sync2cf <repo-path>            # auto-detect prod vs int
python -m sync2cf --dry-run <repo-path>  # preview, no API calls
python -m sync2cf --space MYSPACE .      # override space
python -m sync2cf --prefix "DEV" .       # override auto-prefix
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CONFLUENCE_PROD_HOST` | `https://atc.bmwgroup.net/confluence/rest/api` | Production Confluence REST API base URL |
| `CONFLUENCE_PROD_TOKEN` | *(prompt if interactive)* | PAT for production writes |
| `CONFLUENCE_INT_HOST` | Falls back to `CONFLUENCE_PROD_HOST` | Integration Confluence REST API base URL |
| `CONFLUENCE_INT_TOKEN` | Falls back to `CONFLUENCE_PROD_TOKEN` | PAT for integration writes |
| `CONFLUENCE_READONLY_HOST` | — | Read-only Confluence host (all GET requests routed here) |
| `CONFLUENCE_READONLY_TOKEN` | — | PAT for read-only host |
| `CONFLUENCE_SPACE` | *(required)* | Confluence space key |

Values can also be placed in a `.env` file at the working directory.

## Prod vs Integration Logic

| Condition | Write target | Prefix |
|---|---|---|
| On default branch, clean, up-to-date with remote | **Prod** (`CONFLUENCE_PROD_HOST`) | *(none)* |
| Feature branch / dirty tree / behind remote | **Integration** (`CONFLUENCE_INT_HOST`, falls back to Prod) | Branch name |

When `CONFLUENCE_INT_HOST` / `CONFLUENCE_INT_TOKEN` are not set, they default to their `PROD` counterparts — so a single token is enough if you use the same Confluence instance for both.

## Page Hierarchy

All root-level pages from the repo are created as **children of the Confluence space's home page**. Subdirectories become nested child pages, preserving the repo's folder structure. The space home page itself is never modified.

## Read-Only Routing

When `CONFLUENCE_READONLY_HOST` and `CONFLUENCE_READONLY_TOKEN` are set, all Confluence **read** operations (page lookups, space info, attachment checks) are routed to the read-only instance. Writes always go to the effective write host.

## Using sync2cf in Your Repo

Add a workflow to your repo that checks out sync2cf and runs it against your own working tree:

```yaml
# .github/workflows/sync-docs.yml
name: Sync2Confluence

on:
  push:
    branches: [main]
    paths: ['README.md', 'doc/**']
  pull_request:
    branches: [main]
    paths: ['README.md', 'doc/**']
  workflow_dispatch:

permissions:
  contents: read

jobs:
  sync-docs:
    runs-on: bmw-ubuntu-24.04-medium
    timeout-minutes: 30
    steps:
      - name: Checkout your repo
        uses: actions/checkout@v5

      - name: Checkout sync2cf
        uses: actions/checkout@v5
        with:
          repository: ToolsArsenal/sync2cf
          path: .sync2cf
          token: ${{ secrets.REPO_ACCESS_TOKEN }}

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Install sync2cf
        run: uv sync --frozen --project .sync2cf

      - name: Sync2Confluence
        env:
          CONFLUENCE_PROD_TOKEN: ${{ secrets.CONFLUENCE_PROD_TOKEN }}
          CONFLUENCE_SPACE: ${{ vars.CONFLUENCE_SPACE }}
        run: |
          DRY_RUN=""
          [ "${{ github.event_name }}" = "pull_request" ] && DRY_RUN="--dry-run"
          uv run --project .sync2cf sync2cf $DRY_RUN .
```

## Setup (Local)

```bash
uv sync              # install project + deps
uv sync --extra dev  # include dev/test deps
```

## Project Structure

```
sync2cf/
├── __init__.py
├── __main__.py              # CLI entry point
├── config.py                # Pydantic settings from env vars / .env
├── confluence.py            # md2cf orchestration
├── git_info.py              # Git branch, remote, dirty detection
├── postface.py              # Postface template rendering
├── preface.md               # Warning banner prepended to every page
└── postface.md.template     # Metadata footer appended to every page
```
