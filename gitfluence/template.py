"""Render preface / postface templates with git & host information."""

from __future__ import annotations

import getpass
import socket
from datetime import datetime, timezone

from gitfluence.git_info import GitInfo


def render_template(template: str, git_info: GitInfo) -> str:
    """Fill ``{placeholder}`` tokens in a template string.

    Supported placeholders: ``{repo_origin}``, ``{branch_name}``,
    ``{username}``, ``{hostname}``, ``{timestamp}``.
    """
    replacements = {
        "{repo_origin}": git_info.origin_url,
        "{branch_name}": git_info.branch_name,
        "{username}": getpass.getuser(),
        "{hostname}": socket.gethostname(),
        "{timestamp}": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result
