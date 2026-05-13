# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Full mdfluence CLI option parity: `--disable-emoji`, `--disable-anchor-convert`, `--render-diagrams`, `--mmdc-path`, `--plantuml-path`, `--title`, `--parent-id`, `--parent-title`, `--top-level`, `--insecure`, `--content-type`
- `--host-int`, `--token-int`, `--username-int`, `--password-int` for integration target auth
- `--debug` alias for `--verbose` (mdfluence compat), `-n` alias for `--dry-run`
- Branch grouping page (`Branch: {branch-name}`) under integration root — all content pages for a branch are now children of this page
- `--no-preface` / `--no-postface` flags to disable bundled defaults
- Template placeholder support (`{branch_name}`, `{repo_origin}`, `{username}`, `{hostname}`, `{timestamp}`) for all preface/postface sources (CLI string, file, and bundled defaults)
- Sync markdown files from a git repo to Confluence as a page hierarchy
- Automatic prod vs integration routing based on git branch state
- Pass-through support for all mdfluence CLI options
- Composite GitHub Action for consumer repos (replaces reusable workflow)
- Bundled preface/postface templates with git metadata
- Relative link resolution across pages
- Integration root page isolation for feature branches
- PyPI Trusted Publishers (OIDC) for secure publishing
- Digital attestations for published packages
- Release candidate workflow via bump2version and TestPyPI
- Initial public release of gitfluence

### Changed

- **Breaking:** `CONFLUENCE_PROD_HOST` renamed to `CONFLUENCE_HOST`; `CONFLUENCE_PROD_TOKEN` renamed to `CONFLUENCE_TOKEN`; `action.yml` inputs renamed accordingly
- **Breaking:** CLI parser now inherits mdfluence `get_parser()` — full CLI option parity with mdfluence
- **Breaking:** Integration page titles no longer carry the branch name as prefix; the branch page provides hierarchy context instead
- **Breaking:** `render_postface` moved from `gitfluence.postface` to `gitfluence.template.render_template`; `postface.py` removed
- Preface is now a template (`preface.md` → `preface.md.template`) with `{repo_origin}` and `{branch_name}` placeholders
- Auth model: token > username+password > interactive prompt > dry-run dummy
- Release scripts renamed: `prepare-release.sh` → `merge-bump.sh`, `commit-release.sh` → `publish-release.sh`
- `deploy-test.yml` trigger narrowed from `v*` to `v*-rc*` (RC tags only)

### Fixed

- `--ignore-relative-link-errors` flag now correctly respected during sync
