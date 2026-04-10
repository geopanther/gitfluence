"""Configuration for sync2cf using pydantic-settings.

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

DEFAULT_DUMMY_TOKEN = "dummy"
DEFAULT_DRY_RUN_SPACE = "DRY_RUN"


def _prompt_text(env_name: str) -> str:
    return f"{env_name} (or set before run): "


class Sync2CfSettings(BaseSettings):
    """Environment-driven configuration for Confluence sync."""

    model_config = SettingsConfigDict()

    # ── Confluence hosts & tokens ──────────────────────────────────────
    confluence_prod_host: str = "https://atc.bmwgroup.net/confluence/rest/api"
    confluence_prod_token: Optional[SecretStr] = None

    confluence_int_host: Optional[str] = (
        "https://atc-int.bmwgroup.net/confluence/rest/api"
    )
    confluence_int_token: Optional[SecretStr] = None

    confluence_space: Optional[str] = None


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

        # ── INT defaults to PROD host when not explicitly set ─────────
        int_host = settings.confluence_int_host or settings.confluence_prod_host
        prod_token = settings.confluence_prod_token

        # ── Effective write target ─────────────────────────────────────
        if use_prod:
            self.write_host: str = settings.confluence_prod_host
            self.write_token = self._require_token(
                prod_token,
                "CONFLUENCE_PROD_TOKEN",
                dry_run=dry_run,
            )
            self.prefix: Optional[str] = None
        else:
            self.write_host = int_host
            self.write_token = self._require_token(
                settings.confluence_int_token,
                "CONFLUENCE_INT_TOKEN",
                dry_run=dry_run,
            )
            self.prefix = branch_name

        self.space = self._require_space(settings.confluence_space, dry_run=dry_run)

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _require_token(
        token: Optional[SecretStr], env_name: str, *, dry_run: bool
    ) -> SecretStr:
        if token is not None:
            return token
        if dry_run:
            return SecretStr(DEFAULT_DUMMY_TOKEN)
        if not sys.stdin.isatty():
            raise SystemExit(
                f"ERROR: {env_name} is not set and stdin is not a terminal."
            )
        value = getpass.getpass(_prompt_text(env_name))
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
            return DEFAULT_DRY_RUN_SPACE
        if not sys.stdin.isatty():
            raise SystemExit(
                "ERROR: CONFLUENCE_SPACE is not set and stdin is not a terminal."
            )
        value = input(_prompt_text("CONFLUENCE_SPACE")).strip()
        if not value:
            raise SystemExit("ERROR: CONFLUENCE_SPACE cannot be empty.")
        os.environ["CONFLUENCE_SPACE"] = value
        return value
