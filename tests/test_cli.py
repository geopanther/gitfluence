"""Unit tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gitfluence.__main__ import _build_parser, main


# ── Helper: parse args via _build_parser ──────────────────────────────────


def _parse(argv: list[str]):
    """Parse argv through gitfluence's parser and return the namespace."""
    parser = _build_parser()
    return parser.parse_args(argv)


# ── 1a. mdfluence parser args inherited correctly ─────────────────────────


class TestInheritedArgs:
    def test_content_type_choices_enforced(self):
        with pytest.raises(SystemExit):
            _parse(["--content-type", "foo", "."])
        args = _parse(["--content-type", "blogpost", "."])
        assert args.content_type == "blogpost"

    def test_mdfluence_flags_parse(self):
        args = _parse(
            [
                "--beautify-folders",
                "--collapse-empty",
                "--ignore-relative-link-errors",
                "--insecure",
                ".",
            ]
        )
        assert args.beautify_folders is True
        assert args.collapse_empty is True
        assert args.ignore_relative_link_errors is True
        assert args.insecure is True

    def test_mutual_exclusion_parent(self):
        with pytest.raises(SystemExit):
            _parse(["--parent-title", "X", "--parent-id", "Y", "."])

    def test_mutual_exclusion_dir_titles(self):
        with pytest.raises(SystemExit):
            _parse(["--beautify-folders", "--use-pages-file", "."])

    def test_mutual_exclusion_empty(self):
        with pytest.raises(SystemExit):
            _parse(["--collapse-empty", "--skip-empty", "."])


# ── 1b. gitfluence default overrides ──────────────────────────────────────


class TestDefaultOverrides:
    def test_default_only_changed_true(self):
        args = _parse(["."])
        assert args.only_changed is True

    def test_default_strip_top_header_true(self):
        args = _parse(["."])
        assert args.strip_top_header is True

    def test_default_collapse_single_pages_true(self):
        args = _parse(["."])
        assert args.collapse_single_pages is True

    def test_default_skip_empty_true(self):
        args = _parse(["."])
        assert args.skip_empty is True

    def test_default_skip_subtrees_wo_markdown_true(self):
        args = _parse(["."])
        assert args.skip_subtrees_wo_markdown is True

    def test_default_enable_relative_links_true(self):
        args = _parse(["."])
        assert args.enable_relative_links is True

    def test_default_max_retries_unchanged(self):
        args = _parse(["."])
        assert args.max_retries == 4

    def test_default_convert_anchors_true(self):
        args = _parse(["."])
        assert args.convert_anchors is True


# ── 1c. gitfluence-specific args ─────────────────────────────────────────


class TestGitfluenceArgs:
    def test_verbose_flag(self):
        args = _parse(["-v", "."])
        assert args.verbose is True

    def test_verbose_long(self):
        args = _parse(["--verbose", "."])
        assert args.verbose is True

    def test_debug_alias_for_verbose(self):
        args = _parse(["--debug", "."])
        assert args.verbose is True

    def test_no_preface_flag(self):
        args = _parse(["--no-preface", "."])
        assert args.no_preface is True

    def test_no_postface_flag(self):
        args = _parse(["--no-postface", "."])
        assert args.no_postface is True

    def test_repo_path_positional(self):
        args = _parse(["/some/path"])
        assert isinstance(args.repo_path, Path)
        assert str(args.repo_path) == "/some/path"

    def test_dry_run_shorthand_n(self):
        args = _parse(["-n", "."])
        assert args.dry_run is True

    def test_host_int_arg(self):
        args = _parse(["--host-int", "https://int.example.com", "."])
        assert args.host_int == "https://int.example.com"

    def test_token_int_arg(self):
        args = _parse(["--token-int", "tok-int", "."])
        assert args.token_int == "tok-int"

    def test_username_int_arg(self):
        args = _parse(["--username-int", "user-int", "."])
        assert args.username_int == "user-int"

    def test_password_int_arg(self):
        args = _parse(["--password-int", "pw-int", "."])
        assert args.password_int == "pw-int"


# ── 1d. mdfluence-only args removed ──────────────────────────────────────


class TestRemovedArgs:
    def test_no_output_arg(self):
        with pytest.raises(SystemExit):
            _parse(["--output", "json", "."])

    def test_no_file_list_positional(self):
        """repo_path is single Path, not nargs=* file_list."""
        args = _parse(["."])
        assert hasattr(args, "repo_path")
        assert not hasattr(args, "file_list")


# ── 1e. Auth args work ───────────────────────────────────────────────────


class TestAuthArgs:
    def test_host_arg_parses(self):
        args = _parse(["--host", "https://prod.example.com", "."])
        assert args.host == "https://prod.example.com"

    def test_host_short_o(self):
        args = _parse(["-o", "https://prod.example.com", "."])
        assert args.host == "https://prod.example.com"

    def test_token_arg_parses(self):
        args = _parse(["--token", "my-token", "."])
        assert args.token == "my-token"

    def test_username_arg_parses(self):
        args = _parse(["--username", "user", "."])
        assert args.username == "user"

    def test_username_short_u(self):
        args = _parse(["-u", "user", "."])
        assert args.username == "user"

    def test_password_arg_parses(self):
        args = _parse(["--password", "pw", "."])
        assert args.password == "pw"

    def test_password_short_p(self):
        args = _parse(["-p", "pw", "."])
        assert args.password == "pw"

    def test_insecure_arg_parses(self):
        args = _parse(["--insecure", "."])
        assert args.insecure is True

    def test_page_id_rejected(self, tmp_repo, monkeypatch, capsys):
        monkeypatch.setenv("CONFLUENCE_HOST", "https://prod.example.com/api")
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_HOST", raising=False)
        with pytest.raises(SystemExit):
            main(["--dry-run", "--page-id", "123", str(tmp_repo)])
        err = capsys.readouterr().err
        assert "--page-id" in err
        assert "--parent-id" in err


# ── 1j. page-id rejected ─────────────────────────────────────────────────


class TestPageIdRejected:
    def test_page_id_rejected_with_message(self, tmp_repo, monkeypatch, capsys):
        monkeypatch.setenv("CONFLUENCE_HOST", "https://prod.example.com/api")
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_HOST", raising=False)
        with pytest.raises(SystemExit):
            main(["--dry-run", "--page-id", "123", str(tmp_repo)])
        err = capsys.readouterr().err
        assert "--parent-id" in err


# ── 1k. Preface/postface (existing tests adapted) ────────────────────────


def _env_for_dry_run(monkeypatch):
    """Set minimal env for dry-run CLI tests."""
    monkeypatch.setenv("CONFLUENCE_HOST", "https://prod.example.com/api")
    for v in ["CONFLUENCE_TOKEN", "CONFLUENCE_INT_TOKEN", "CONFLUENCE_INT_HOST"]:
        monkeypatch.delenv(v, raising=False)


class TestCLI:
    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_nonexistent_path_exits(self, tmp_path):
        bad = tmp_path / "no-such-dir"
        with pytest.raises(SystemExit):
            main([str(bad)])

    def test_dry_run_no_api_calls(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", str(tmp_repo)])
            mock_sync.assert_called_once()
            ctx = mock_sync.call_args[0][0]
            assert ctx.dry_run is True
            assert ctx.write_token.get_secret_value() == "dummy"


class TestNoPreface:
    def test_no_preface_disables_default(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", "--no-preface", str(tmp_repo)])
            mock_sync.assert_called_once()
            preface_markup = mock_sync.call_args[0][1]
            assert preface_markup == ""

    def test_no_postface_disables_default(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", "--no-postface", str(tmp_repo)])
            mock_sync.assert_called_once()
            postface_markup = mock_sync.call_args[0][2]
            assert postface_markup == ""

    def test_default_preface_not_empty(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", str(tmp_repo)])
            mock_sync.assert_called_once()
            preface_markup = mock_sync.call_args[0][1]
            assert preface_markup != ""

    def test_default_postface_not_empty(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", str(tmp_repo)])
            mock_sync.assert_called_once()
            postface_markup = mock_sync.call_args[0][2]
            assert postface_markup != ""


class TestPrefixOverride:
    def test_prefix_override_sets_context(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", "--prefix", "custom-branch", str(tmp_repo)])
            ctx = mock_sync.call_args[0][0]
            assert ctx.prefix == "custom-branch"

    def test_empty_prefix_forces_prod(self, tmp_repo, monkeypatch):
        _env_for_dry_run(monkeypatch)
        with patch("gitfluence.__main__.run_sync") as mock_sync:
            main(["--dry-run", "--prefix", "", str(tmp_repo)])
            ctx = mock_sync.call_args[0][0]
            assert ctx.prefix is None
