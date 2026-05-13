from datetime import datetime, timedelta, timezone

from crypto_farmer.signals.models import NewsItem
from tests.fakes.news import FakeNewsSource


def test_fake_news_filters_since():
    now = datetime.now(timezone.utc)
    items = [
        NewsItem(source="x", url="a", title="vieja", body=None,
                 published_at=now - timedelta(hours=6), related_pairs=[]),
        NewsItem(source="x", url="b", title="reciente", body=None,
                 published_at=now - timedelta(hours=1), related_pairs=[]),
    ]
    fake = FakeNewsSource(items=items)
    result = fake.fetch_recent(since=now - timedelta(hours=4))
    assert [i.title for i in result] == ["reciente"]
