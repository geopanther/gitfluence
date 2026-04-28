"""Configuration for gitfluence using pydantic-settings.

All values read from environment variables.
Env var naming matches mdfluence for prod (CONFLUENCE_HOST, CONFLUENCE_TOKEN, etc.)
and adds CONFLUENCE_INT_* variants for integration target.
"""

from __future__ import annotations

import getpass
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

DEFAULT_DUMMY_HOST = "https://dummy.example.com/api"
DEFAULT_DUMMY_SECRET = "dummy"  # nosec B105 - not a real secret, placeholder for dry-run
DEFAULT_DUMMY_SPACE = "DRY_RUN"


class GitfluenceSettings(BaseSettings):
    """Environment-driven configuration for Confluence sync."""

    model_config = SettingsConfigDict()

    # ── Prod connection (matches mdfluence naming) ─────────────────────
    confluence_host: Optional[str] = None
    confluence_token: Optional[SecretStr] = None
    confluence_username: Optional[str] = None
    confluence_password: Optional[SecretStr] = None

    # ── Integration connection ─────────────────────────────────────────
    confluence_int_host: Optional[str] = None
    confluence_int_token: Optional[SecretStr] = None
    confluence_int_username: Optional[str] = None
    confluence_int_password: Optional[SecretStr] = None

    # ── Space ──────────────────────────────────────────────────────────
    confluence_space: Optional[str] = None


class GitfluenceContext:
    """Runtime context assembled from settings + git state + CLI args.

    Config priority: CLI arg > env var > interactive prompt > dry-run dummy.
    Auth decision (per resolved target): token > username+password.
    """

    def __init__(
        self,
        settings: GitfluenceSettings,
        *,
        repo_path: Path,
        use_prod: bool,
        branch_name: str,
        dry_run: bool = False,
        # CLI overrides (highest priority)
        cli_host: Optional[str] = None,
        cli_token: Optional[str] = None,
        cli_username: Optional[str] = None,
        cli_password: Optional[str] = None,
        cli_host_int: Optional[str] = None,
        cli_token_int: Optional[str] = None,
        cli_username_int: Optional[str] = None,
        cli_password_int: Optional[str] = None,
        cli_space: Optional[str] = None,
        cli_insecure: bool = False,
    ) -> None:
        self.settings = settings
        self.repo_path = repo_path
        self.dry_run = dry_run
        self.insecure = cli_insecure

        if use_prod:
            self._resolve_prod(
                settings, dry_run, cli_host, cli_token, cli_username, cli_password
            )
            self.prefix: Optional[str] = None
        else:
            self._resolve_int(
                settings,
                dry_run,
                cli_host,
                cli_token,
                cli_username,
                cli_password,
                cli_host_int,
                cli_token_int,
                cli_username_int,
                cli_password_int,
            )
            self.prefix = branch_name

        self.space = self._resolve_space(
            cli_space or settings.confluence_space, dry_run=dry_run
        )

    # ── Prod resolution ───────────────────────────────────────────────

    def _resolve_prod(
        self,
        s: GitfluenceSettings,
        dry_run: bool,
        cli_host: Optional[str],
        cli_token: Optional[str],
        cli_username: Optional[str],
        cli_password: Optional[str],
    ) -> None:
        self.write_host: str = self._require_host(
            cli_host or s.confluence_host,
            "CONFLUENCE_HOST",
            dry_run=dry_run,
        )
        self._resolve_auth(
            env_token=s.confluence_token,
            env_username=s.confluence_username,
            env_password=s.confluence_password,
            cli_token=cli_token,
            cli_username=cli_username,
            cli_password=cli_password,
            token_env_name="CONFLUENCE_TOKEN",  # nosec B106 - env var name, not password
            dry_run=dry_run,
        )

    # ── Int resolution ────────────────────────────────────────────────

    def _resolve_int(
        self,
        s: GitfluenceSettings,
        dry_run: bool,
        cli_host: Optional[str],
        cli_token: Optional[str],
        cli_username: Optional[str],
        cli_password: Optional[str],
        cli_host_int: Optional[str],
        cli_token_int: Optional[str],
        cli_username_int: Optional[str],
        cli_password_int: Optional[str],
    ) -> None:
        # Determine if a separate int host is configured
        int_host = cli_host_int or s.confluence_int_host

        if int_host:
            # Separate int target → enforce int-specific auth
            log.info("Int mode: using separate int host %s", int_host)
            self.write_host = int_host
            self._resolve_auth(
                env_token=s.confluence_int_token,
                env_username=s.confluence_int_username,
                env_password=s.confluence_int_password,
                cli_token=cli_token_int,
                cli_username=cli_username_int,
                cli_password=cli_password_int,
                token_env_name="CONFLUENCE_INT_TOKEN",  # nosec B106 - env var name
                dry_run=dry_run,
            )
        else:
            # No separate int host → full fallback to prod config
            log.info("Int mode: no int host configured, falling back to prod config")
            self.write_host = self._require_host(
                cli_host or s.confluence_host,
                "CONFLUENCE_HOST",
                dry_run=dry_run,
            )
            self._resolve_auth(
                env_token=s.confluence_token,
                env_username=s.confluence_username,
                env_password=s.confluence_password,
                cli_token=cli_token,
                cli_username=cli_username,
                cli_password=cli_password,
                token_env_name="CONFLUENCE_TOKEN",  # nosec B106 - env var name
                dry_run=dry_run,
            )

    # ── Auth decision (matching mdfluence): token > user+password ─────

    def _resolve_auth(
        self,
        *,
        env_token: Optional[SecretStr],
        env_username: Optional[str],
        env_password: Optional[SecretStr],
        cli_token: Optional[str],
        cli_username: Optional[str],
        cli_password: Optional[str],
        token_env_name: str,
        dry_run: bool,
    ) -> None:
        # Effective values: CLI > env
        token = SecretStr(cli_token) if cli_token else env_token
        username = cli_username or env_username
        password = SecretStr(cli_password) if cli_password else env_password

        if token:
            # Token auth wins
            self.write_token: Optional[SecretStr] = token
            self.write_username: Optional[str] = None
            self.write_password: Optional[SecretStr] = None
        elif username and password:
            # Basic auth fallback
            self.write_token = None
            self.write_username = username
            self.write_password = password
        elif username and not password:
            # Username given but no password — prompt for it
            pw_env = token_env_name.replace("_TOKEN", "_PASSWORD")
            self.write_token = None
            self.write_username = username
            self.write_password = self._require_secret(None, pw_env, dry_run=dry_run)
        elif dry_run:
            self.write_token = SecretStr(DEFAULT_DUMMY_SECRET)
            self.write_username = None
            self.write_password = None
        else:
            # Try prompting for token
            self.write_token = self._require_secret(None, token_env_name, dry_run=False)
            self.write_username = None
            self.write_password = None

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
        value = input(GitfluenceContext._prompt_text(env_name)).strip()
        if not value:
            raise SystemExit(f"ERROR: {env_name} cannot be empty.")
        os.environ[env_name] = value
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
    def _resolve_space(space: Optional[str], *, dry_run: bool) -> str:
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
