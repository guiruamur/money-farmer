from __future__ import annotations

from typing import Protocol

import pandas as pd

from crypto_farmer.signals.models import Ticker


class MarketDataSource(Protocol):
    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        """Devuelve un DataFrame con columnas timestamp, open, high, low, close, volume."""

    def fetch_ticker(self, pair: str) -> Ticker:
        ...
