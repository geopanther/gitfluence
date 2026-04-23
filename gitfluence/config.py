"""Configuration for gitfluence using pydantic-settings.

All values read from environment variables.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DUMMY_HOST = "https://dummy.example.com/api"
DEFAULT_DUMMY_SECRET = "dummy"  # nosec B105 - not a real secret, placeholder for dry-run
DEFAULT_DUMMY_SPACE = "DRY_RUN"


class GitfluenceSettings(BaseSettings):
    """Environment-driven configuration for Confluence sync."""

    model_config = SettingsConfigDict()

    # ── Confluence hosts & tokens ──────────────────────────────────────
    confluence_prod_host: Optional[str] = None
    confluence_prod_token: Optional[SecretStr] = None

    confluence_int_host: Optional[str] = None
    confluence_int_token: Optional[SecretStr] = None

    confluence_space: Optional[str] = None


class GitfluenceContext:
    """Runtime context assembled from settings + git state + CLI args.

    Passed as single parameter to every function that needs configuration.
    """

    def __init__(
        self,
        settings: GitfluenceSettings,
        *,
        repo_path: Path,
        use_prod: bool,
        branch_name: str,
        dry_run: bool = False,
    ) -> None:
        self.settings = settings
        self.repo_path = repo_path
        self.dry_run = dry_run

        # ── INT defaults to PROD host when not explicitly set ─────────
        int_host = settings.confluence_int_host or settings.confluence_prod_host
        prod_token = settings.confluence_prod_token

        # ── Effective write target ─────────────────────────────────────
        if use_prod:
            self.write_host: str = self._require_host(
                settings.confluence_prod_host,
                "CONFLUENCE_PROD_HOST",
                dry_run=dry_run,
            )
            self.write_token = self._require_secret(
                prod_token,
                "CONFLUENCE_PROD_TOKEN",
                dry_run=dry_run,
            )
            self.prefix: Optional[str] = None
        else:
            self.write_host = self._require_host(
                int_host,
                "CONFLUENCE_INT_HOST / CONFLUENCE_PROD_HOST",
                dry_run=dry_run,
            )
            self.write_token = self._require_secret(
                settings.confluence_int_token,
                "CONFLUENCE_INT_TOKEN",
                dry_run=dry_run,
            )
            self.prefix = branch_name

        self.space = self._require_space(settings.confluence_space, dry_run=dry_run)

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _prompt_text(env_name: str) -> str:
        return f"{env_name} (or set before run): "

    @staticmethod
    def _require_host(host: Optional[str], env_name: str, *, dry_run: bool) -> str:
        if host is not None:
            return host
        if dry_run:
            return DEFAULT_DUMMY_HOST
        if not sys.stdin.isatty():
            raise SystemExit(
                f"ERROR: {env_name} is not set and stdin is not a terminal."
            )
        value = input(GitfluenceContext._prompt_text("CONFLUENCE_PROD_HOST")).strip()
        if not value:
            raise SystemExit("ERROR: CONFLUENCE_PROD_HOST cannot be empty.")
        os.environ["CONFLUENCE_PROD_HOST"] = value
        return value

    @staticmethod
    def _require_secret(
        secret: Optional[SecretStr], env_name: str, *, dry_run: bool
    ) -> SecretStr:
        if secret is not None:
            return secret
        if dry_run:
            return SecretStr(DEFAULT_DUMMY_SECRET)
        if not sys.stdin.isatty():
            raise SystemExit(
                f"ERROR: {env_name} is not set and stdin is not a terminal."
            )
        value = getpass.getpass(GitfluenceContext._prompt_text(env_name))
        if not value:
            raise SystemExit(f"ERROR: {env_name} cannot be empty.")
        env_var_name = env_name.split(" ", maxsplit=1)[0]
        os.environ[env_var_name] = value
        return SecretStr(value)

    @staticmethod
    def _require_space(space: Optional[str], *, dry_run: bool) -> str:
        if space:
            return space
        if dry_run:
            return DEFAULT_DUMMY_SPACE
        if not sys.stdin.isatty():
            raise SystemExit(
                "ERROR: CONFLUENCE_SPACE is not set and stdin is not a terminal."
            )
        value = input(GitfluenceContext._prompt_text("CONFLUENCE_SPACE")).strip()
        if not value:
            raise SystemExit("ERROR: CONFLUENCE_SPACE cannot be empty.")
        os.environ["CONFLUENCE_SPACE"] = value
        return value
