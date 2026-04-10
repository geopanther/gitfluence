"""Unit tests for the CLI entry point."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sync2cf.__main__ import main


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
        monkeypatch.delenv("CONFLUENCE_PROD_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_READONLY_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_INT_HOST", raising=False)
        with patch("sync2cf.__main__.run_sync") as mock_sync:
            main(["--dry-run", str(tmp_repo)])
            mock_sync.assert_called_once()
            ctx = mock_sync.call_args[0][0]
            assert ctx.dry_run is True
            assert ctx.write_token.get_secret_value() == "dummy"
