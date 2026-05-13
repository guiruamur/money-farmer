from unittest.mock import MagicMock

import pandas as pd
import pytest

from crypto_farmer.data.market import CcxtBinanceSource, MarketFetchError


def _make_ccxt(ohlcv_rows=None, ticker=None, raises=None):
    fake = MagicMock()
    if raises:
        fake.fetch_ohlcv.side_effect = raises
        fake.fetch_ticker.side_effect = raises
    else:
        fake.fetch_ohlcv.return_value = ohlcv_rows or []
        fake.fetch_ticker.return_value = ticker or {}
    return fake


def test_fetch_ohlcv_returns_dataframe():
    raw = [
        [1700000000000, 100.0, 110.0, 95.0, 105.0, 10.0],
        [1700000900000, 105.0, 112.0, 104.0, 110.0, 12.0],
    ]
    exchange = _make_ccxt(ohlcv_rows=raw)
    src = CcxtBinanceSource(exchange=exchange)

    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=200)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["close"].iloc[-1] == 110.0
    exchange.fetch_ohlcv.assert_called_once_with("BTC/USDT", "15m", limit=200)


def test_fetch_ticker_returns_model():
    exchange = _make_ccxt(ticker={"last": 42000.5, "timestamp": 1700000000000})
    src = CcxtBinanceSource(exchange=exchange)
    t = src.fetch_ticker("BTC/USDT")
    assert t.price == 42000.5
    assert t.pair == "BTC/USDT"
    assert t.timestamp.tzinfo is not None  # always UTC-aware


def test_fetch_raises_market_fetch_error_on_ccxt_failure():
    exchange = _make_ccxt(raises=RuntimeError("network down"))
    src = CcxtBinanceSource(exchange=exchange)
    with pytest.raises(MarketFetchError):
        src.fetch_ohlcv("BTC/USDT", "15m", lookback=10)
    with pytest.raises(MarketFetchError):
        src.fetch_ticker("BTC/USDT")
