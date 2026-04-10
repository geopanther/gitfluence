"""Unit tests for sync2cf.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from sync2cf.config import Sync2CfContext, Sync2CfSettings


class TestSync2CfSettings:
    def test_defaults_match_builtin_defaults(self, monkeypatch):
        for name in [
            "CONFLUENCE_PROD_HOST",
            "CONFLUENCE_PROD_TOKEN",
            "CONFLUENCE_INT_HOST",
            "CONFLUENCE_INT_TOKEN",
            "CONFLUENCE_READONLY_HOST",
            "CONFLUENCE_READONLY_TOKEN",
            "CONFLUENCE_SPACE",
        ]:
            monkeypatch.delenv(name, raising=False)

        s = Sync2CfSettings()

        assert s.confluence_prod_host == "https://atc.bmwgroup.net/confluence/rest/api"
        assert s.confluence_prod_token is None
        assert (
            s.confluence_int_host == "https://atc-int.bmwgroup.net/confluence/rest/api"
        )
        assert s.confluence_int_token is None
        assert s.confluence_readonly_host is None
        assert s.confluence_readonly_token is None
        assert s.confluence_space is None

    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_PROD_HOST", "https://prod.example.com/api")
        monkeypatch.setenv("CONFLUENCE_PROD_TOKEN", "tok-prod")
        monkeypatch.setenv("CONFLUENCE_SPACE", "MYSPACE")
        s = Sync2CfSettings()
        assert s.confluence_prod_host == "https://prod.example.com/api"
        assert s.confluence_prod_token.get_secret_value() == "tok-prod"
        assert s.confluence_space == "MYSPACE"

    def test_int_token_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        s = Sync2CfSettings()
        assert s.confluence_int_token is None


class TestSync2CfContext:
    @staticmethod
    def _make_settings(**overrides):
        defaults = {
            "confluence_prod_host": "https://prod.example.com/api",
            "confluence_prod_token": SecretStr("tok-prod"),
            "confluence_int_host": None,
            "confluence_int_token": None,
            "confluence_readonly_host": None,
            "confluence_readonly_token": None,
            "confluence_space": "SP",
        }
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
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feat/x",
            dry_run=True,
        )
        # INT host falls back to PROD in dry-run; token becomes dummy.
        assert ctx.write_host == "https://prod.example.com/api"
        assert ctx.write_token.get_secret_value() == "dummy"
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
        s = self._make_settings(confluence_readonly_host=None)
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.read_host is None
        assert ctx.read_token is None

    def test_readonly_token_falls_back_to_prod(self):
        s = self._make_settings(
            confluence_readonly_host="https://ro.example.com/api",
            confluence_readonly_token=None,
        )
        ctx = Sync2CfContext(
            s, repo_path=Path("/tmp"), use_prod=True, branch_name="main"
        )
        assert ctx.read_token.get_secret_value() == "tok-prod"

    def test_missing_token_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_prod_token=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_PROD_TOKEN"):
            Sync2CfContext(s, repo_path=Path("/tmp"), use_prod=True, branch_name="main")

    def test_missing_token_dry_run_uses_dummy(self):
        s = self._make_settings(
            confluence_prod_token=None,
            confluence_int_token=None,
            confluence_readonly_token=None,
        )
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.write_token.get_secret_value() == "dummy"
        assert ctx.read_token is None

    def test_prompt_prod_token_exports(self, monkeypatch):
        prompts = []

        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: True})())
        monkeypatch.setattr(
            "sync2cf.config.getpass.getpass",
            lambda prompt: prompts.append(prompt) or "tok-prompt",
        )
        monkeypatch.delenv("CONFLUENCE_PROD_TOKEN", raising=False)
        s = self._make_settings(
            confluence_prod_token=None, confluence_readonly_token=None
        )
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=False,
        )
        assert ctx.write_token.get_secret_value() == "tok-prompt"
        assert ctx.read_token is None
        assert os.environ["CONFLUENCE_PROD_TOKEN"] == "tok-prompt"
        assert prompts == ["CONFLUENCE_PROD_TOKEN (or set before run): "]

    def test_missing_int_token_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_int_token=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_INT_TOKEN"):
            Sync2CfContext(
                s,
                repo_path=Path("/tmp"),
                use_prod=False,
                branch_name="feature/x",
            )

    def test_prompt_int_token_exports(self, monkeypatch):
        prompts = []

        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: True})())
        monkeypatch.setattr(
            "sync2cf.config.getpass.getpass",
            lambda prompt: prompts.append(prompt) or "tok-int",
        )
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        s = self._make_settings(confluence_int_token=None)
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=False,
            branch_name="feature/x",
        )
        assert ctx.write_token.get_secret_value() == "tok-int"
        assert os.environ["CONFLUENCE_INT_TOKEN"] == "tok-int"
        assert prompts == ["CONFLUENCE_INT_TOKEN (or set before run): "]

    def test_missing_space_non_interactive(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: False})())
        s = self._make_settings(confluence_space=None)
        with pytest.raises(SystemExit, match="CONFLUENCE_SPACE"):
            Sync2CfContext(s, repo_path=Path("/tmp"), use_prod=True, branch_name="main")

    def test_missing_space_dry_run_uses_default(self):
        s = self._make_settings(confluence_space=None)
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
            dry_run=True,
        )
        assert ctx.space == "DRY_RUN"

    def test_prompt_space_exports(self, monkeypatch):
        prompts = []

        monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": lambda s: True})())
        monkeypatch.setattr(
            "builtins.input", lambda prompt: prompts.append(prompt) or "MYSPACE"
        )
        monkeypatch.delenv("CONFLUENCE_SPACE", raising=False)
        s = self._make_settings(confluence_space=None)
        ctx = Sync2CfContext(
            s,
            repo_path=Path("/tmp"),
            use_prod=True,
            branch_name="main",
        )
        assert ctx.space == "MYSPACE"
        assert os.environ["CONFLUENCE_SPACE"] == "MYSPACE"
        assert prompts == ["CONFLUENCE_SPACE (or set before run): "]

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
