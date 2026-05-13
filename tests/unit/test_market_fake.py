import pandas as pd
from datetime import datetime, timezone

from tests.fakes.market import FakeMarketDataSource


def test_fake_returns_configured_ohlcv():
    df = pd.DataFrame([
        {"timestamp": 1, "open": 100, "high": 110, "low": 95, "close": 105, "volume": 10},
        {"timestamp": 2, "open": 105, "high": 112, "low": 104, "close": 110, "volume": 12},
    ])
    fake = FakeMarketDataSource(ohlcv={"BTC/USDT": df})
    out = fake.fetch_ohlcv("BTC/USDT", "15m", lookback=200)
    assert list(out.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(out) == 2


def test_fake_returns_configured_ticker():
    ts = datetime.now(timezone.utc)
    fake = FakeMarketDataSource(tickers={"BTC/USDT": (42000.0, ts)})
    t = fake.fetch_ticker("BTC/USDT")
    assert t.price == 42000.0
    assert t.timestamp == ts


def test_fake_raises_on_unknown_pair():
    fake = FakeMarketDataSource(ohlcv={})
    import pytest
    with pytest.raises(KeyError):
        fake.fetch_ohlcv("UNKNOWN/USDT", "15m", lookback=200)


def test_fake_ticker_raises_on_unknown_pair():
    fake = FakeMarketDataSource(tickers={})
    import pytest
    with pytest.raises(KeyError):
        fake.fetch_ticker("UNKNOWN/USDT")
