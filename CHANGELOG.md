# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Branch grouping page (`Branch: {branch-name}`) under integration root — all content pages for a branch are now children of this page

### Changed

- **Breaking:** Integration page titles no longer carry the branch name as prefix; the branch page provides hierarchy context instead
- `--no-preface` / `--no-postface` flags to disable bundled defaults
- Template placeholder support (`{branch_name}`, `{repo_origin}`, `{username}`, `{hostname}`, `{timestamp}`) for all preface/postface sources (CLI string, file, and bundled defaults)
- Initial public release of gitfluence

### Changed

- Preface is now a template (`preface.md` → `preface.md.template`) with `{repo_origin}` and `{branch_name}` placeholders
- `render_postface` moved from `gitfluence.postface` to `gitfluence.template.render_template`; `postface.py` removed

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
