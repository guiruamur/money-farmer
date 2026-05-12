from __future__ import annotations

from datetime import datetime

import pandas as pd

from crypto_farmer.signals.models import Ticker


class FakeMarketDataSource:
    def __init__(
        self,
        *,
        ohlcv: dict[str, pd.DataFrame] | None = None,
        tickers: dict[str, tuple[float, datetime]] | None = None,
    ) -> None:
        self._ohlcv = ohlcv or {}
        self._tickers = tickers or {}

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        if pair not in self._ohlcv:
            raise KeyError(pair)
        return self._ohlcv[pair].tail(lookback).reset_index(drop=True).copy()

    def fetch_ticker(self, pair: str) -> Ticker:
        if pair not in self._tickers:
            raise KeyError(pair)
        price, ts = self._tickers[pair]
        return Ticker(pair=pair, price=price, timestamp=ts)
