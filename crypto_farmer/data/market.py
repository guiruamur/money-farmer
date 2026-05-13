from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import pandas as pd

from crypto_farmer.signals.models import Ticker


class MarketDataSource(Protocol):
    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        """Devuelve un DataFrame con columnas timestamp, open, high, low, close, volume."""

    def fetch_ticker(self, pair: str) -> Ticker:
        ...


class MarketFetchError(Exception):
    pass


class CcxtBinanceSource:
    """Adaptador sobre un exchange ccxt (inyectable). En producción se pasa ccxt.binance()."""

    def __init__(self, exchange) -> None:
        self._exchange = exchange

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        try:
            rows = self._exchange.fetch_ohlcv(pair, timeframe, limit=lookback)
        except Exception as e:
            raise MarketFetchError(f"fetch_ohlcv {pair} {timeframe}: {e}") from e
        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        # CCXT returns timestamps as ms epoch ints. Convert to UTC-aware pandas Timestamps
        # so downstream code (indicators, situation) can treat them as datetimes.
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    def fetch_ticker(self, pair: str) -> Ticker:
        try:
            raw = self._exchange.fetch_ticker(pair)
        except Exception as e:
            raise MarketFetchError(f"fetch_ticker {pair}: {e}") from e
        ts_ms = raw.get("timestamp")
        ts = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            if ts_ms
            else datetime.now(timezone.utc)
        )
        return Ticker(pair=pair, price=float(raw["last"]), timestamp=ts)
