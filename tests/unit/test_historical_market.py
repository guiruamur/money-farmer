from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import HistoricalMarketSource
from crypto_farmer.clock import BacktestClock


def _df():
    base = datetime(2026, 5, 17, tzinfo=timezone.utc)
    rows = [
        {"timestamp": pd.Timestamp(base) + pd.Timedelta(minutes=15 * i),
         "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 10}
        for i in range(10)
    ]
    return pd.DataFrame(rows)


def test_fetch_ohlcv_never_returns_future_candles():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 0, 45, tzinfo=timezone.utc)  # 4th candle (i=3)
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=100)
    assert df["timestamp"].max() <= pd.Timestamp(clock.current)
    assert len(df) == 4  # candles i=0..3


def test_fetch_ohlcv_respects_lookback():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 2, 0, tzinfo=timezone.utc)  # i=8
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=3)
    assert len(df) == 3
    assert df["close"].iloc[-1] == 100 + 8


def test_fetch_ticker_returns_current_candle_close():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 0, 30, tzinfo=timezone.utc)  # i=2
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    t = src.fetch_ticker("BTC/USDT")
    assert t.price == 100 + 2
