"""Unit tests for gitfluence.postface."""

# pylint: disable=duplicate-code

from __future__ import annotations

import re

from gitfluence.git_info import GitInfo
from gitfluence.postface import render_postface


class TestRenderPostface:
    @staticmethod
    def _git_info():
        return GitInfo(
            origin_url="git@github.com:org/repo.git",
            branch_name="main",
            default_branch="main",
            is_default_branch=True,
            is_clean=True,
            is_up_to_date=True,
        )

    def test_placeholders_filled(self):
        template = (
            "> Generated from `{repo_origin}` | Branch: `{branch_name}` "
            "| By `{username}@{hostname}` @ {timestamp}\n"
        )
        result = render_postface(template, self._git_info())
        assert "git@github.com:org/repo.git" in result
        assert "main" in result
        assert "@" in result  # username@hostname
        assert re.search(r"\d{4}-\d{2}-\d{2}", result)  # timestamp

    def test_no_leftover_braces(self):
        template = "{repo_origin} {branch_name} {username} {hostname} {timestamp}"
        result = render_postface(template, self._git_info())
        assert "{" not in result
        assert "}" not in result

    def test_branch_name_in_output(self):
        template = "branch={branch_name}"
        info = GitInfo(
            origin_url="x",
            branch_name="feat/cool-thing",
            default_branch="main",
            is_default_branch=False,
            is_clean=True,
            is_up_to_date=False,
        )
        result = render_postface(template, info)
        assert result == "branch=feat/cool-thing"
