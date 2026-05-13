"""Unit tests for gitfluence.config."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from gitfluence.config import (
    DEFAULT_DUMMY_HOST,
    DEFAULT_DUMMY_SECRET,
    DEFAULT_DUMMY_SPACE,
    GitfluenceContext,
    GitfluenceSettings,
)


# ── GitfluenceSettings env var tests ──────────────────────────────────────


class TestGitfluenceSettings:
    @staticmethod
    def _clear_env(monkeypatch):
        for name in [
            "CONFLUENCE_HOST",
            "CONFLUENCE_TOKEN",
            "CONFLUENCE_USERNAME",
            "CONFLUENCE_PASSWORD",
            "CONFLUENCE_INT_HOST",
            "CONFLUENCE_INT_TOKEN",
            "CONFLUENCE_INT_USERNAME",
            "CONFLUENCE_INT_PASSWORD",
            "CONFLUENCE_SPACE",
            # also clear old names in case they leak
            "CONFLUENCE_PROD_HOST",
            "CONFLUENCE_PROD_TOKEN",
        ]:
            monkeypatch.delenv(name, raising=False)

    def test_nothing_from_env(self, monkeypatch):
        self._clear_env(monkeypatch)
        s = GitfluenceSettings()
        assert s.confluence_host is None
        assert s.confluence_token is None
        assert s.confluence_username is None
        assert s.confluence_password is None
        assert s.confluence_int_host is None
        assert s.confluence_int_token is None
        assert s.confluence_int_username is None
        assert s.confluence_int_password is None
        assert s.confluence_space is None

    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_HOST", "https://prod.example.com/api")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "tok-prod")
        monkeypatch.setenv("CONFLUENCE_USERNAME", "user-prod")
        monkeypatch.setenv("CONFLUENCE_PASSWORD", "pw-prod")
        monkeypatch.setenv("CONFLUENCE_SPACE", "MYSPACE")
        monkeypatch.setenv("CONFLUENCE_INT_HOST", "https://int.example.com/api")
        monkeypatch.setenv("CONFLUENCE_INT_TOKEN", "tok-int")
        monkeypatch.setenv("CONFLUENCE_INT_USERNAME", "user-int")
        monkeypatch.setenv("CONFLUENCE_INT_PASSWORD", "pw-int")
        s = GitfluenceSettings()
        assert s.confluence_host == "https://prod.example.com/api"
        assert s.confluence_token.get_secret_value() == "tok-prod"
        assert s.confluence_username == "user-prod"
        assert s.confluence_password.get_secret_value() == "pw-prod"
        assert s.confluence_int_host == "https://int.example.com/api"
        assert s.confluence_int_token.get_secret_value() == "tok-int"
        assert s.confluence_int_username == "user-int"
        assert s.confluence_int_password.get_secret_value() == "pw-int"
        assert s.confluence_space == "MYSPACE"


# ── GitfluenceContext tests ───────────────────────────────────────────────


class TestGitfluenceContext:
    @staticmethod
    def _make_settings(**overrides):
        defaults = {
            "confluence_host": "https://prod.example.com/api",
            "confluence_token": SecretStr("tok-prod"),
            "confluence_username": None,
            "confluence_password": None,
            "confluence_int_host": None,
            "confluence_int_token": None,
            "confluence_int_username": None,
            "confluence_int_password": None,
            "confluence_space": "SP",
        }
        defaults.update(overrides)
        return GitfluenceSettings(**defaults)

    # ── 1f. Prod-update-mode config resolution ────────────────────────

    def test_prod_host_from_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_host == "https://prod.example.com/api"

    def test_prod_host_cli_overrides_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            cli_host="https://cli-host.example.com",
        )
        assert ctx.write_host == "https://cli-host.example.com"

    def test_prod_token_from_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_token.get_secret_value() == "tok-prod"

    def test_prod_token_cli_overrides_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            cli_token="tok-cli",
        )
        assert ctx.write_token.get_secret_value() == "tok-cli"

    def test_prod_username_password_from_env(self):
        s = self._make_settings(
            confluence_token=None,
            confluence_username="user",
            confluence_password=SecretStr("pw"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_username == "user"
        assert ctx.write_password.get_secret_value() == "pw"
        assert ctx.write_token is None

    def test_space_from_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.space == "SP"

    def test_space_cli_overrides_env(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            cli_space="OVERRIDE",
        )
        assert ctx.space == "OVERRIDE"

    # ── 1g. Int-update-mode, NO int host → full prod fallback ─────────

    def test_int_no_int_host_uses_prod_host(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
            dry_run=True,
        )
        assert ctx.write_host == "https://prod.example.com/api"

    def test_int_no_int_host_uses_prod_token(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
        )
        assert ctx.write_token.get_secret_value() == "tok-prod"

    def test_int_no_int_host_uses_prod_username(self):
        s = self._make_settings(
            confluence_token=None,
            confluence_username="user-prod",
            confluence_password=SecretStr("pw-prod"),
        )
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
        )
        assert ctx.write_username == "user-prod"

    def test_int_no_int_host_cli_host_falls_back(self):
        s = self._make_settings(confluence_host=None)
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
            cli_host="https://cli.example.com",
        )
        assert ctx.write_host == "https://cli.example.com"

    def test_int_no_int_host_cli_token_falls_back(self):
        s = self._make_settings(confluence_token=None)
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
            cli_token="tok-cli",
        )
        assert ctx.write_token.get_secret_value() == "tok-cli"

    # ── 1h. Int-update-mode, int host configured → enforce int auth ───

    def test_int_with_int_host_uses_int_host(self):
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=SecretStr("tok-int"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
        )
        assert ctx.write_host == "https://int.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-int"

    def test_int_with_int_host_enforces_int_auth(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=None,
            confluence_int_username=None,
            confluence_int_password=None,
        )
        with pytest.raises(SystemExit):
            GitfluenceContext(
                s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
            )

    def test_int_with_int_host_uses_int_token(self):
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=SecretStr("tok-int"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
        )
        assert ctx.write_token.get_secret_value() == "tok-int"

    def test_int_with_int_host_uses_int_username_password(self):
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=None,
            confluence_int_username="user-int",
            confluence_int_password=SecretStr("pw-int"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
        )
        assert ctx.write_username == "user-int"
        assert ctx.write_password.get_secret_value() == "pw-int"

    def test_int_host_int_cli_overrides_env(self):
        s = self._make_settings(
            confluence_int_host="https://int-env.example.com/api",
            confluence_int_token=SecretStr("tok-int"),
        )
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="dev",
            cli_host_int="https://int-cli.example.com/api",
            cli_token_int="tok-int-cli",
        )
        assert ctx.write_host == "https://int-cli.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-int-cli"

    # ── 1i. Auth decision logic ───────────────────────────────────────

    def test_token_auth_preferred_over_password(self):
        s = self._make_settings(
            confluence_username="user",
            confluence_password=SecretStr("pw"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        # Token takes precedence
        assert ctx.write_token.get_secret_value() == "tok-prod"
        assert ctx.write_username is None
        assert ctx.write_password is None

    def test_basic_auth_when_no_token(self):
        s = self._make_settings(
            confluence_token=None,
            confluence_username="user",
            confluence_password=SecretStr("pw"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_token is None
        assert ctx.write_username == "user"
        assert ctx.write_password.get_secret_value() == "pw"

    def test_username_without_password_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(
            confluence_token=None,
            confluence_username="user",
            confluence_password=None,
        )
        with pytest.raises(SystemExit):
            GitfluenceContext(
                s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
            )

    def test_username_without_password_dry_run(self):
        s = self._make_settings(
            confluence_token=None,
            confluence_username="user",
            confluence_password=None,
        )
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.write_username == "user"
        assert ctx.write_password.get_secret_value() == "dummy"

    # ── Existing tests (updated for new env var names) ────────────────

    def test_prod_mode(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_host == "https://prod.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-prod"
        assert ctx.prefix is None

    def test_prod_mode_dry_run_defaults(self):
        s = GitfluenceSettings()
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main", dry_run=True
        )
        assert ctx.write_host == DEFAULT_DUMMY_HOST
        assert ctx.write_token.get_secret_value() == DEFAULT_DUMMY_SECRET
        assert ctx.space == DEFAULT_DUMMY_SPACE

    def test_int_mode_falls_back_to_prod(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
        )
        # No int host → uses prod host and token
        assert ctx.write_host == "https://prod.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-prod"
        assert ctx.prefix == "feat/x"

    def test_int_mode_explicit(self):
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=SecretStr("tok-int"),
        )
        ctx = GitfluenceContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
        )
        assert ctx.write_host == "https://int.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-int"
        assert ctx.prefix == "dev"

    def test_missing_host_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_host=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_HOST"):
            GitfluenceContext(
                s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
            )

    def test_missing_token_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_token=None)
        with pytest.raises(SystemExit):
            GitfluenceContext(
                s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
            )

    def test_missing_token_dry_run_uses_dummy(self):
        s = self._make_settings(
            confluence_token=None,
            confluence_int_token=None,
        )
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.write_token.get_secret_value() == "dummy"

    def test_missing_space_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_space=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_SPACE"):
            GitfluenceContext(
                s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
            )

    def test_missing_space_dry_run_uses_default(self):
        s = self._make_settings(confluence_space=None)
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.space == "DRY_RUN"

    def test_dry_run_flag(self):
        s = self._make_settings()
        ctx = GitfluenceContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.dry_run is True
