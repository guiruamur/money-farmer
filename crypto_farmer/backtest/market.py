from __future__ import annotations

from datetime import datetime

import pandas as pd

from crypto_farmer.clock import Clock  # noqa: F401
from crypto_farmer.signals.models import Ticker  # noqa: F401

_TF_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}
_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


class OhlcvStore:
    """Downloads and caches historical OHLCV for a date range, paginating ccxt."""

    def __init__(self, *, exchange, page_limit: int = 1000) -> None:
        self._ex = exchange
        self._page = page_limit

    def load(self, *, pair: str, timeframe: str, since: datetime, until: datetime) -> pd.DataFrame:
        step = _TF_MS[timeframe]
        cursor = int(since.timestamp() * 1000)
        end_ms = int(until.timestamp() * 1000)
        rows: list[list] = []
        while cursor <= end_ms:
            page = self._ex.fetch_ohlcv(pair, timeframe, since=cursor, limit=self._page)
            if not page:
                break
            rows.extend(page)
            last = page[-1][0]
            if last < cursor:  # no progress -> stop
                break
            cursor = last + step
            if len(page) < self._page and cursor > end_ms:
                break
        df = pd.DataFrame(rows, columns=_COLS).drop_duplicates(subset="timestamp")
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df[df["timestamp"] <= pd.Timestamp(until)].reset_index(drop=True)
        return df
