"""Render the postface template with git / host information."""

from __future__ import annotations

import getpass
import socket
from datetime import datetime, timezone

from sync2cf.git_info import GitInfo


def render_postface(template: str, git_info: GitInfo) -> str:
    """Fill ``{placeholder}`` tokens in a postface template string."""
    return template.format(
        repo_origin=git_info.origin_url,
        branch_name=git_info.branch_name,
        username=getpass.getuser(),
        hostname=socket.gethostname(),
        timestamp=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
