# gitfluence

Sync markdown files from any git repo working tree to Confluence as a page hierarchy.

Uses [mdfluence](https://github.com/geopanther/mdfluence) for markdown → Confluence conversion and upload. All mdfluence CLI options can be passed through gitfluence.

## Installation

```bash
pip install gitfluence
```

## Usage

```bash
gitfluence <repo-path>                   # auto-detect prod vs int
gitfluence --dry-run <repo-path>         # preview, no API calls
gitfluence --space MYSPACE .             # override space
gitfluence --prefix "DEV" .              # override auto-prefix
gitfluence --beautify-folders .          # pass mdfluence options
```

## Environment Variables

| Variable                | Required | Description                                                 |
| ----------------------- | -------- | ----------------------------------------------------------- |
| `CONFLUENCE_PROD_HOST`  | Yes      | Production Confluence REST API base URL                     |
| `CONFLUENCE_PROD_TOKEN` | Yes\*    | PAT for production writes                                   |
| `CONFLUENCE_INT_HOST`   | No       | Integration Confluence REST API base URL (defaults to prod) |
| `CONFLUENCE_INT_TOKEN`  | No\*     | PAT for integration writes                                  |
| `CONFLUENCE_SPACE`      | Yes\*    | Confluence space key                                        |

\* On `--dry-run`, missing host defaults to `https://dummy.example.com/api`, missing tokens default to `dummy` and missing space defaults to `DRY_RUN`. In interactive mode, missing values are prompted.

Copy `setenv.example.sh` to `setenv.sh` and fill in your values:

```bash
cp setenv.example.sh setenv.sh
# Edit setenv.sh with your Confluence details
source setenv.sh
```

## Prod vs Integration Logic

| Condition                                        | Write target    | Prefix      |
| ------------------------------------------------ | --------------- | ----------- |
| On default branch, clean, up-to-date with remote | **Prod**        | _(none)_    |
| Feature branch / dirty tree / behind remote      | **Integration** | Branch name |

## Page Hierarchy

All root-level pages from the repo are created as children of the Confluence space's home page. Subdirectories become nested child pages.

In integration mode (feature branches), an empty root page named after the repository directory is created under the space's home page. All integration pages are placed as children of this root page.

## Reusable Workflow

Consumer repos can integrate with a single `uses:` line:

```yaml
name: Sync to Confluence

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  sync:
    uses: geopanther/gitfluence/.github/workflows/reusable-sync.yml@main
    with:
      repo_path: "."
      extra_args: "--beautify-folders"
    secrets:
      CONFLUENCE_PROD_HOST: ${{ secrets.CONFLUENCE_PROD_HOST }}
      CONFLUENCE_PROD_TOKEN: ${{ secrets.CONFLUENCE_PROD_TOKEN }}
      CONFLUENCE_SPACE: ${{ secrets.CONFLUENCE_SPACE }}
```

### Workflow inputs

| Input                | Default           | Description                           |
| -------------------- | ----------------- | ------------------------------------- |
| `repo_path`          | `"."`             | Root directory to sync                |
| `dry_run`            | `false`           | Preview mode                          |
| `gitfluence_version` | `"latest"`        | Version to install                    |
| `runner`             | `"ubuntu-latest"` | Runner label (GHE users can override) |
| `python_version`     | `"3.12"`          | Python version                        |
| `extra_args`         | `""`              | Additional CLI args                   |

## CLI Options (mdfluence pass-through)

gitfluence supports all mdfluence options. Key groups:

**Page information:** `--title`, `--content-type`, `--message`, `--minor-edit`, `--strip-top-header`, `--remove-text-newlines`, `--replace-all-labels`

**Parent selection** (mutually exclusive): `--parent-title` / `--parent-id` / `--top-level`

**Preface** (mutually exclusive): `--preface-markdown` / `--preface-file`

**Postface** (mutually exclusive): `--postface-markdown` / `--postface-file`

**Directory:** `--collapse-single-pages`, `--no-gitignore`, `--skip-subtrees-wo-markdown`

**Directory titles** (mutually exclusive): `--beautify-folders` / `--use-pages-file`

**Empty dirs** (mutually exclusive): `--collapse-empty` / `--skip-empty`

**Relative links:** `--enable-relative-links`, `--ignore-relative-link-errors`

**Anchors:** `--convert-anchors` / `--no-convert-anchors`

**General:** `--only-changed`, `--max-retries`

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
