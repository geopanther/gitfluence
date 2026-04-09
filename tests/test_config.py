"""Unit tests for sync2cf.config."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from sync2cf.config import Sync2CfContext, Sync2CfSettings


class TestSync2CfSettings:
    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_PROD_HOST", "https://prod.example.com/api")
        monkeypatch.setenv("CONFLUENCE_PROD_TOKEN", "tok-prod")
        monkeypatch.setenv("CONFLUENCE_SPACE", "MYSPACE")
        s = Sync2CfSettings()
        assert s.confluence_prod_host == "https://prod.example.com/api"
        assert s.confluence_prod_token.get_secret_value() == "tok-prod"
        assert s.confluence_space == "MYSPACE"

    def test_int_defaults_to_none(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_PROD_HOST", "https://prod.example.com/api")
        monkeypatch.setenv("CONFLUENCE_PROD_TOKEN", "tok")
        monkeypatch.setenv("CONFLUENCE_SPACE", "SP")
        monkeypatch.delenv("CONFLUENCE_INT_HOST", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        s = Sync2CfSettings()
        assert s.confluence_int_host is None
        assert s.confluence_int_token is None


class TestSync2CfContext:
    @staticmethod
    def _make_settings(**overrides):
        defaults = dict(
            confluence_prod_host="https://prod.example.com/api",
            confluence_prod_token=SecretStr("tok-prod"),
            confluence_int_host=None,
            confluence_int_token=None,
            confluence_space="SP",
        )
        defaults.update(overrides)
        return Sync2CfSettings(**defaults)

    def test_prod_mode(self):
        s = self._make_settings()
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.write_host == "https://prod.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-prod"
        assert ctx.prefix is None

    def test_int_mode_falls_back_to_prod(self):
        s = self._make_settings()
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="feat/x"
        )
        # INT not set → falls back to PROD
        assert ctx.write_host == "https://prod.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-prod"
        assert ctx.prefix == "feat/x"

    def test_int_mode_explicit(self):
        s = self._make_settings(
            confluence_int_host="https://int.example.com/api",
            confluence_int_token=SecretStr("tok-int"),
        )
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=False, branch_name="dev"
        )
        assert ctx.write_host == "https://int.example.com/api"
        assert ctx.write_token.get_secret_value() == "tok-int"
        assert ctx.prefix == "dev"

    def test_readonly_routing(self):
        s = self._make_settings(
            confluence_readonly_host="https://ro.example.com/api",
            confluence_readonly_token=SecretStr("tok-ro"),
        )
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.read_host == "https://ro.example.com/api"
        assert ctx.read_token.get_secret_value() == "tok-ro"

    def test_no_readonly(self):
        s = self._make_settings()
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.read_host is None
        assert ctx.read_token is None

    def test_missing_token_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_prod_token=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_PROD_TOKEN"):
            Sync2CfContext(s, repo_path=Path("/tmp"), use_prod=True, branch_name="main")

    def test_dry_run_flag(self):
        s = self._make_settings()
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.dry_run is True
