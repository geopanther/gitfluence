# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Initial public release of gitfluence
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
