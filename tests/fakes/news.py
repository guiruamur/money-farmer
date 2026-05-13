from __future__ import annotations

from datetime import datetime

from crypto_farmer.signals.models import NewsItem


class FakeNewsSource:
    def __init__(self, *, items: list[NewsItem] | None = None) -> None:
        self._items = items or []

    def fetch_recent(self, since: datetime) -> list[NewsItem]:
        return [i for i in self._items if i.published_at >= since]
