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

Copy `setenv.example.ps1` to `setenv.ps1` and fill in your values:

```powershell
Copy-Item setenv.example.ps1 setenv.ps1
```

Edit setenv.ps1 with your Confluence details.

```powershell
. .\setenv.ps1
```

</details>

## Prod vs Integration Logic

| Condition                                        | Write target    | Prefix   |
| ------------------------------------------------ | --------------- | -------- |
| On default branch, clean, up-to-date with remote | **Prod**        | _(none)_ |
| Feature branch / dirty tree / behind remote      | **Integration** | _(none)_ |

## Page Hierarchy

All root-level pages from the repo are created as children of the Confluence space's home page. Subdirectories become nested child pages.

In integration mode (feature branches), the following hierarchy is created:

```
Space Homepage
  └── {repo-name}              (integration root)
       └── Branch: {branch}    (branch grouping page)
            └── Page Title     (content pages)
                 └── Sub Page
```

- **Integration root** — an empty page named after the repository directory, created under the space homepage. Deleting it removes all integration artifacts.
- **Branch page** — an empty page titled `Branch: {branch-name}` under the integration root. Groups all content pages for that branch. Each branch gets its own grouping page.
- **Content pages** — the actual documentation pages, created as children of the branch page with clean titles (no branch prefix).

## GitHub Action

Consumer repos can integrate using the composite action:

```yaml
name: Sync to Confluence

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: geopanther/gitfluence@main
        with:
          repo_path: "."
          extra_args: "--beautify-folders"
          confluence_prod_host: ${{ secrets.CONFLUENCE_PROD_HOST }}
          confluence_prod_token: ${{ secrets.CONFLUENCE_PROD_TOKEN }}
          confluence_space: ${{ secrets.CONFLUENCE_SPACE }}
```

### Action inputs

| Input                   | Default    | Description                      |
| ----------------------- | ---------- | -------------------------------- |
| `repo_path`             | `"."`      | Root directory to sync           |
| `dry_run`               | `"false"`  | Preview mode                     |
| `gitfluence_version`    | `"latest"` | Version to install               |
| `python_version`        | `"3.12"`   | Python version                   |
| `extra_args`            | `""`       | Additional CLI args              |
| `confluence_prod_host`  | —          | Confluence production host URL   |
| `confluence_prod_token` | —          | Confluence production API token  |
| `confluence_int_host`   | `""`       | Confluence integration host URL  |
| `confluence_int_token`  | `""`       | Confluence integration API token |
| `confluence_space`      | —          | Confluence space key             |

## CLI Options

### gitfluence-specific options

These options are **not** available in mdfluence:

| Option             | Description                                                 |
| ------------------ | ----------------------------------------------------------- |
| `repo_path`        | Root directory of the git working tree to sync (positional) |
| `--space`          | Override Confluence space key                               |
| `--prefix`         | Override auto-detected page title prefix                    |
| `-v` / `--verbose` | Enable debug logging                                        |
| `--no-preface`     | Disable the default preface (DO-NOT-EDIT banner)            |
| `--no-postface`    | Disable the default postface (metadata footer)              |

### Differences from mdfluence defaults

gitfluence changes the following mdfluence defaults to be **enabled by default**:

| Option                        | mdfluence default | gitfluence default |
| ----------------------------- | ----------------- | ------------------ |
| `--strip-top-header`          | off               | **on**             |
| `--only-changed`              | off               | **on**             |
| `--collapse-single-pages`     | off               | **on**             |
| `--skip-empty`                | off               | **on**             |
| `--skip-subtrees-wo-markdown` | off               | **on**             |
| `--enable-relative-links`     | off               | **on**             |

Preface and postface behave differently from mdfluence:

- **mdfluence**: `--preface-markdown` / `--postface-markdown` accept an optional value; when given without a value they default to a static "Contents are auto-generated, do not edit." message. No template placeholders.
- **gitfluence**: Both always require a value. All preface/postface sources (CLI string, file, and bundled defaults) support `{branch_name}`, `{repo_origin}`, `{username}`, `{hostname}`, `{timestamp}` template placeholders. Bundled defaults are richer (repo origin, branch, author, timestamp).

### mdfluence pass-through options

All remaining mdfluence options are passed through unchanged:

**Page information:** `--title`, `--content-type`, `--message`, `--minor-edit`, `--strip-top-header`, `--remove-text-newlines`, `--replace-all-labels`

**Parent selection** (mutually exclusive): `--parent-title` / `--parent-id` / `--top-level`

**Preface** (mutually exclusive): `--preface-markdown` / `--preface-file` / `--no-preface`

> By default a "DO NOT EDIT" banner with repo origin and branch name is prepended.
> All preface sources support `{branch_name}`, `{repo_origin}`, `{username}`, `{hostname}`, `{timestamp}` placeholders.

**Postface** (mutually exclusive): `--postface-markdown` / `--postface-file` / `--no-postface`

> By default a metadata footer with repo origin, branch, author and timestamp is appended.
> All postface sources support the same placeholders as preface.

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
