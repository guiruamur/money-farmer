from __future__ import annotations

from datetime import datetime
from typing import Protocol

import httpx

from crypto_farmer.signals.models import NewsItem


class NewsFetchError(Exception):
    pass


class NewsSource(Protocol):
    def fetch_recent(self, since: datetime) -> list[NewsItem]: ...


class NoopNewsSource:
    """Returns an empty list. Used when news.enabled is False in config."""

    def fetch_recent(self, since: datetime) -> list[NewsItem]:
        return []


class CryptoPanicSource:
    BASE = "https://cryptopanic.com/api/v1/posts/"

    def __init__(self, *, token: str, client: httpx.Client | None = None) -> None:
        self._token = token
        self._client = client or httpx.Client(timeout=15.0)

    def fetch_recent(self, since: datetime) -> list[NewsItem]:
        params = {"auth_token": self._token, "public": "true", "kind": "news"}
        try:
            r = self._client.get(self.BASE, params=params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise NewsFetchError(f"cryptopanic: {e}") from e
        results = r.json().get("results", [])
        items: list[NewsItem] = []
        for raw in results:
            published = datetime.fromisoformat(
                raw["published_at"].replace("Z", "+00:00")
            )
            if published < since:
                continue
            related = [
                f"{c['code']}/USDT" for c in raw.get("currencies", [])
                if c.get("code")
            ]
            items.append(NewsItem(
                source="cryptopanic",
                url=raw["url"],
                title=raw["title"],
                body=raw.get("body"),
                published_at=published,
                related_pairs=related,
            ))
        return items
