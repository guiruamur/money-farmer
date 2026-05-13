from datetime import datetime, timezone

import httpx
import pytest
import respx

from crypto_farmer.data.news import CryptoPanicSource, NewsFetchError


@respx.mock
def test_cryptopanic_parses_response():
    payload = {
        "results": [
            {
                "id": 1,
                "title": "BTC rompe máximos",
                "url": "https://cryptopanic.com/news/1",
                "published_at": "2026-05-12T10:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
            {
                "id": 2,
                "title": "ETH update",
                "url": "https://cryptopanic.com/news/2",
                "published_at": "2026-05-12T09:30:00Z",
                "currencies": [{"code": "ETH"}],
            },
        ]
    }
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(200, json=payload)
    )

    src = CryptoPanicSource(token="abc", client=httpx.Client())
    items = src.fetch_recent(since=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc))

    assert len(items) == 2
    assert items[0].title == "BTC rompe máximos"
    assert items[0].related_pairs == ["BTC/USDT"]
    assert items[1].related_pairs == ["ETH/USDT"]


@respx.mock
def test_cryptopanic_raises_on_http_error():
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(500)
    )
    src = CryptoPanicSource(token="abc", client=httpx.Client())
    with pytest.raises(NewsFetchError):
        src.fetch_recent(since=datetime(2026, 5, 12, tzinfo=timezone.utc))


@respx.mock
def test_cryptopanic_filters_by_since():
    payload = {
        "results": [
            {
                "id": 1, "title": "old", "url": "u1",
                "published_at": "2026-05-12T08:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
            {
                "id": 2, "title": "new", "url": "u2",
                "published_at": "2026-05-12T10:00:00Z",
                "currencies": [{"code": "BTC"}],
            },
        ]
    }
    respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(200, json=payload)
    )
    src = CryptoPanicSource(token="abc", client=httpx.Client())
    items = src.fetch_recent(since=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc))
    assert [i.title for i in items] == ["new"]
