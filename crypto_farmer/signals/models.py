from __future__ import annotations

from datetime import datetime
from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TimeHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CycleStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class Signal(BaseModel):
    action: SignalAction
    confidence: int = Field(ge=0, le=100)
    reasoning: str = Field(max_length=500)
    entry_price_hint: float | None
    invalidation_level: float | None
    time_horizon: TimeHorizon
    key_factors: list[str] = Field(max_length=5)


class Ticker(BaseModel):
    pair: str
    price: float
    timestamp: datetime


class NewsItem(BaseModel):
    source: str
    url: str
    title: str
    body: str | None
    published_at: datetime
    related_pairs: list[str] = Field(default_factory=list)


class IndicatorSnapshot(BaseModel):
    pair: str
    timestamp: datetime
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    ema_20: float
    ema_50: float
    bb_upper: float
    bb_lower: float
    atr: float
    atr_mean_20: float
    volume: float
    volume_mean_24h: float

    def atr_expansion_ratio(self) -> float | None:
        # None signals missing/insufficient mean (data quality issue),
        # which is different from a real "no expansion" signal.
        return self.atr / self.atr_mean_20 if self.atr_mean_20 else None

    def volume_anomaly_ratio(self) -> float | None:
        return self.volume / self.volume_mean_24h if self.volume_mean_24h else None


class OHLCVCandle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVSummary(BaseModel):
    recent: list[OHLCVCandle]
    highest_high: float
    lowest_low: float

    @classmethod
    def from_df(cls, df: pd.DataFrame, *, recent_n: int) -> "OHLCVSummary":
        """Build summary from a DataFrame with columns: open, high, low, close, volume."""
        if df.empty:
            raise ValueError("Cannot build OHLCVSummary from an empty DataFrame")
        tail = df.tail(recent_n)
        recent = [
            OHLCVCandle(
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r["volume"]),
            )
            for _, r in tail.iterrows()
        ]
        return cls(
            recent=recent,
            highest_high=float(tail["high"].max()),
            lowest_low=float(tail["low"].min()),
        )
