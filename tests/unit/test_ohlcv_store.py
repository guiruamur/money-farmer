from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import OhlcvStore


class _FakeExchange:
    """Returns 15m candles as ccxt does: [ms, o, h, l, c, v]."""
    def __init__(self, start_ms, n):
        self.calls = 0
        self._rows = [
            [start_ms + i * 900_000, 100 + i, 101 + i, 99 + i, 100 + i, 10]
            for i in range(n)
        ]
    def fetch_ohlcv(self, pair, timeframe, since=None, limit=None):
        self.calls += 1
        rows = [r for r in self._rows if r[0] >= since]
        return rows[:limit]


def test_store_loads_range_into_dataframe():
    start = datetime(2026, 5, 17, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 6, tzinfo=timezone.utc)  # 6h -> 24 candles
    ex = _FakeExchange(int(start.timestamp() * 1000), n=48)
    store = OhlcvStore(exchange=ex, page_limit=1000)
    df = store.load(pair="BTC/USDT", timeframe="15m", since=start, until=end)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["timestamp"].dt.tz is not None
    assert df["timestamp"].min() >= pd.Timestamp(start)
    assert df["timestamp"].max() <= pd.Timestamp(end)


def test_store_paginates():
    start = datetime(2026, 5, 17, tzinfo=timezone.utc)
    end = datetime(2026, 5, 18, tzinfo=timezone.utc)  # 96 candles
    ex = _FakeExchange(int(start.timestamp() * 1000), n=96)
    store = OhlcvStore(exchange=ex, page_limit=50)  # forces multiple pages
    df = store.load(pair="BTC/USDT", timeframe="15m", since=start, until=end)
    assert ex.calls >= 2
    assert len(df) >= 90
