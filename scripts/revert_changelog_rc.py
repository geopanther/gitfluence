#!/usr/bin/env python
"""Pre-commit hook: revert rc version headings in CHANGELOG.md back to Unreleased.

If bump2version writes a heading like '## 0.1.1-rc1 - 2026-04-16',
this hook reverts it to '## Unreleased' so that only final releases
get permanent version headings in the changelog.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")
RC_HEADING = re.compile(r"^## \d+\.\d+\.\d+-rc\d+ - \d{4}-\d{2}-\d{2}$", re.MULTILINE)


def main() -> int:
    if not CHANGELOG.exists():
        return 0

    text = CHANGELOG.read_text()
    new_text, count = RC_HEADING.subn("## Unreleased", text)

    if count > 0:
        CHANGELOG.write_text(new_text)
        # Re-stage the file so the commit includes the reverted heading
        print(f"Reverted {count} rc heading(s) in CHANGELOG.md back to Unreleased")
        return 1  # Signal pre-commit to re-stage and retry

    return 0


if __name__ == "__main__":
    sys.exit(main())
