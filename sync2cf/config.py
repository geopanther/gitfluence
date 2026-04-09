"""Configuration for sync2cf using pydantic-settings.

All values read from environment variables and/or .env files.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Sync2CfSettings(BaseSettings):
    """Environment-driven configuration for Confluence sync."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── Confluence hosts & tokens ──────────────────────────────────────
    confluence_prod_host: str = "https://atc.bmwgroup.net/confluence/rest/api"
    confluence_prod_token: Optional[SecretStr] = None

    confluence_int_host: Optional[str] = None
    confluence_int_token: Optional[SecretStr] = None

    confluence_readonly_host: Optional[str] = None
    confluence_readonly_token: Optional[SecretStr] = None

    confluence_space: str


class Sync2CfContext:
    """Runtime context assembled from settings + git state + CLI args.

    Passed as single parameter to every function that needs configuration.
    """

    def __init__(
        self,
        settings: Sync2CfSettings,
        *,
        repo_path: Path,
        use_prod: bool,
        branch_name: str,
        dry_run: bool = False,
    ) -> None:
        self.settings = settings
        self.repo_path = repo_path
        self.dry_run = dry_run

        # ── INT defaults to PROD when not explicitly set ─────────────
        int_host = settings.confluence_int_host or settings.confluence_prod_host
        int_token = settings.confluence_int_token or settings.confluence_prod_token

        # ── Effective write target ─────────────────────────────────────
        if use_prod:
            self.write_host: str = settings.confluence_prod_host
            self.write_token: SecretStr = self._require_token(
                settings.confluence_prod_token, "CONFLUENCE_PROD_TOKEN"
            )
            self.prefix: Optional[str] = None
        else:
            self.write_host = int_host
            self.write_token = self._require_token(
                int_token, "CONFLUENCE_INT_TOKEN (falling back to CONFLUENCE_PROD_TOKEN)"
            )
            self.prefix = branch_name

        # ── Effective read target (optional) ───────────────────────────
        if settings.confluence_readonly_host:
            self.read_host: Optional[str] = settings.confluence_readonly_host
            self.read_token: Optional[SecretStr] = self._require_token(
                settings.confluence_readonly_token, "CONFLUENCE_READONLY_TOKEN"
            )
        else:
            self.read_host = None
            self.read_token = None

        self.space: str = settings.confluence_space

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _require_token(
        token: Optional[SecretStr], env_name: str
    ) -> SecretStr:
        if token is not None:
            return token
        if not sys.stdin.isatty():
            raise SystemExit(
                f"ERROR: {env_name} is not set and stdin is not a terminal."
            )
        value = getpass.getpass(f"{env_name}: ")
        if not value:
            raise SystemExit(f"ERROR: {env_name} cannot be empty.")
        return SecretStr(value)
