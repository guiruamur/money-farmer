from datetime import datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from crypto_farmer.signals.models import (
    CycleStatus,
    IndicatorSnapshot,
    NewsItem,
    OHLCVSummary,
    Signal,
    SignalAction,
    Ticker,
    TimeHorizon,
)


def test_signal_valid():
    s = Signal(
        action=SignalAction.BUY,
        confidence=72,
        reasoning="RSI saliendo de sobreventa con MACD cruzando al alza.",
        entry_price_hint=42000.5,
        invalidation_level=41500.0,
        time_horizon=TimeHorizon.SHORT,
        key_factors=["rsi_oversold_reversal", "macd_cross"],
    )
    assert s.action == SignalAction.BUY
    assert s.confidence == 72


def test_signal_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        Signal(
            action=SignalAction.BUY,
            confidence=120,
            reasoning="x",
            entry_price_hint=None,
            invalidation_level=None,
            time_horizon=TimeHorizon.SHORT,
            key_factors=[],
        )


def test_signal_rejects_too_many_factors():
    with pytest.raises(ValidationError):
        Signal(
            action=SignalAction.BUY,
            confidence=60,
            reasoning="x",
            entry_price_hint=None,
            invalidation_level=None,
            time_horizon=TimeHorizon.SHORT,
            key_factors=["a", "b", "c", "d", "e", "f"],
        )


def test_ticker_and_news_item():
    t = Ticker(pair="BTC/USDT", price=42000.0, timestamp=datetime.now(timezone.utc))
    assert t.price == 42000.0

    n = NewsItem(
        source="cryptopanic",
        url="https://example.com/1",
        title="BTC sube",
        body=None,
        published_at=datetime.now(timezone.utc),
        related_pairs=["BTC/USDT"],
    )
    assert n.related_pairs == ["BTC/USDT"]


def test_indicator_snapshot():
    ind = IndicatorSnapshot(
        pair="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        rsi=28.5,
        macd=12.0,
        macd_signal=10.0,
        macd_hist=2.0,
        ema_20=41900.0,
        ema_50=41500.0,
        bb_upper=42500.0,
        bb_lower=41000.0,
        atr=350.0,
        atr_mean_20=300.0,
        volume=125.0,
        volume_mean_24h=80.0,
    )
    assert ind.atr_expansion_ratio() == pytest.approx(350.0 / 300.0)
    assert ind.volume_anomaly_ratio() == pytest.approx(125.0 / 80.0)


def test_indicator_snapshot_zero_means_return_none():
    ind = IndicatorSnapshot(
        pair="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        rsi=50.0, macd=0.0, macd_signal=0.0, macd_hist=0.0,
        ema_20=100.0, ema_50=100.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=10.0, atr_mean_20=0.0,
        volume=100.0, volume_mean_24h=0.0,
    )
    assert ind.atr_expansion_ratio() is None
    assert ind.volume_anomaly_ratio() is None


def test_ohlcv_summary_from_df():
    rows = [
        {"open": 100, "high": 105, "low": 99, "close": 104, "volume": 10},
        {"open": 104, "high": 108, "low": 103, "close": 107, "volume": 12},
    ]
    df = pd.DataFrame(rows)
    s = OHLCVSummary.from_df(df, recent_n=2)
    assert s.recent[0].open == 100
    assert s.recent[-1].close == 107
    assert s.highest_high == 108
    assert s.lowest_low == 99


def test_ohlcv_summary_rejects_empty_df():
    df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    with pytest.raises(ValueError):
        OHLCVSummary.from_df(df, recent_n=2)


def test_cycle_status_enum():
    assert CycleStatus.OK.value == "ok"
    assert CycleStatus.DEGRADED.value == "degraded"
    assert CycleStatus.FAILED.value == "failed"
