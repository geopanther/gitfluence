"""In-memory mock of mdfluence.api.MinimalConfluence for integration testing.

Implements the subset of the MinimalConfluence API that gitfluence uses,
backed by plain dicts so no HTTP calls are needed.
"""

from __future__ import annotations

import itertools
from typing import Any


class Bunch(dict):
    """Attribute-accessible dict, matching mdfluence.api.Bunch."""

    def __init__(self, kwargs: dict | None = None):
        if kwargs is None:
            kwargs = {}
        converted = {}
        for key, value in kwargs.items():
            if isinstance(value, dict):
                converted[key] = Bunch(value)
            elif isinstance(value, list):
                converted[key] = [
                    Bunch(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                converted[key] = value
        super().__init__(converted)
        self.__dict__ = self


class MockConfluence:
    """In-memory Confluence API that stores pages and attachments."""

    def __init__(self, *, space_key: str = "TEST", homepage_id: int = 1):
        self._id_seq = itertools.count(homepage_id + 1)
        self._space_key = space_key
        self._homepage_id = homepage_id

        # page store: id → Bunch
        self._pages: dict[int, Bunch] = {
            homepage_id: Bunch(
                {
                    "id": homepage_id,
                    "title": "Home",
                    "type": "page",
                    "space": {"key": space_key},
                    "body": {"storage": {"value": "", "representation": "storage"}},
                    "version": {"number": 1, "message": ""},
                    "ancestors": [],
                    "metadata": {"labels": {"results": []}},
                    "_links": {
                        "base": "http://mock.example.com",
                        "webui": f"/spaces/{space_key}/pages/{homepage_id}",
                    },
                }
            )
        }

        # attachment store: (page_id, filename) → Bunch
        self._attachments: dict[tuple[int, str], Bunch] = {}

    # ── Space ─────────────────────────────────────────────────────────

    def get_space(
        self, space: str, additional_expansions: list[str] | None = None
    ) -> Bunch:
        return Bunch(
            {
                "key": space,
                "homepage": {"id": self._homepage_id},
            }
        )

    # ── Pages ─────────────────────────────────────────────────────────

    def get_page(
        self,
        title: str | None = None,
        space_key: str | None = None,
        page_id: int | None = None,
        content_type: str | None = None,
        additional_expansions: list[str] | None = None,
    ) -> Bunch | None:
        if page_id is not None:
            return self._pages.get(page_id)
        if title is not None:
            for page in self._pages.values():
                if page.title == title and (
                    space_key is None or page.space.key == space_key
                ):
                    if content_type is None or page.get("type") == content_type:
                        return page
        return None

    def create_page(
        self,
        space: str,
        title: str,
        body: str,
        content_type: str = "page",
        parent_id: int | None = None,
        update_message: str | None = None,
        labels: list[str] | None = None,
    ) -> Bunch:
        page_id = next(self._id_seq)
        ancestors = []
        if parent_id is not None:
            ancestors = [{"id": parent_id}]
        page = Bunch(
            {
                "id": page_id,
                "title": title,
                "type": content_type,
                "space": {"key": space},
                "body": {"storage": {"value": body, "representation": "storage"}},
                "version": {"number": 1, "message": update_message or ""},
                "ancestors": ancestors,
                "metadata": {
                    "labels": {
                        "results": [
                            {"name": label, "type": "global"}
                            for label in (labels or [])
                        ]
                    }
                },
                "_links": {
                    "base": "http://mock.example.com",
                    "webui": f"/spaces/{space}/pages/{page_id}",
                },
            }
        )
        self._pages[page_id] = page
        return page

    def update_page(
        self,
        page: Bunch,
        body: str,
        parent_id: int | None = None,
        update_message: str | None = None,
        labels: list[str] | None = None,
        minor_edit: bool = False,
    ) -> Bunch:
        page.body = Bunch(
            {"storage": {"value": body, "representation": "storage"}}
        )
        page.version = Bunch(
            {
                "number": page.version.number + 1,
                "message": update_message or "",
                "minorEdit": minor_edit,
            }
        )
        if parent_id is not None:
            page.ancestors = [Bunch({"id": parent_id})]
        if labels is not None:
            page.metadata.labels.results = [
                Bunch({"name": label, "type": "global"}) for label in labels
            ]
        return page

    def add_labels(self, page: Bunch, labels: list[str]) -> Any:
        existing = {r.name for r in page.metadata.labels.results}
        for label in labels:
            if label not in existing:
                page.metadata.labels.results.append(
                    Bunch({"name": label, "type": "global"})
                )

    # ── Attachments ───────────────────────────────────────────────────

    def get_attachment(self, confluence_page: Bunch, name: str) -> Bunch | None:
        return self._attachments.get((confluence_page.id, name))

    def create_attachment(
        self, confluence_page: Bunch, fp: Any, message: str = ""
    ) -> Bunch:
        att_id = next(self._id_seq)
        name = getattr(fp, "name", f"attachment-{att_id}")
        att = Bunch({"id": att_id, "title": name})
        self._attachments[(confluence_page.id, name)] = att
        return att

    def update_attachment(
        self,
        confluence_page: Bunch,
        fp: Any,
        existing_attachment: Bunch,
        message: str = "",
    ) -> Bunch:
        return existing_attachment

    # ── Links ─────────────────────────────────────────────────────────

    def get_url(self, page: Bunch) -> str:
        return f"{page._links.base}{page._links.webui}"

    # ── Inspection helpers (for test assertions) ──────────────────────

    @property
    def pages(self) -> dict[int, Bunch]:
        """All stored pages by ID."""
        return dict(self._pages)

    def get_page_by_title(self, title: str) -> Bunch | None:
        """Convenience: find page by exact title."""
        for page in self._pages.values():
            if page.title == title:
                return page
        return None

    def get_children(self, parent_id: int) -> list[Bunch]:
        """All pages whose ancestors include *parent_id*."""
        result = []
        for page in self._pages.values():
            if any(a.id == parent_id for a in page.ancestors):
                result.append(page)
        return result
