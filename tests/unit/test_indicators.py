from datetime import datetime, timezone

import numpy as np
import pandas as pd

from crypto_farmer.analysis.indicators import IndicatorEngine


def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": base + rng.normal(0, 0.5, n),
        "high": base + np.abs(rng.normal(0, 1, n)) + 1,
        "low": base - np.abs(rng.normal(0, 1, n)) - 1,
        "close": base,
        "volume": rng.uniform(50, 150, n),
    })
    return df


def test_compute_returns_snapshot():
    engine = IndicatorEngine()
    df = _make_ohlcv(120)
    snap = engine.compute("BTC/USDT", df)
    assert snap.pair == "BTC/USDT"
    assert 0 <= snap.rsi <= 100
    assert snap.ema_20 > 0
    assert snap.ema_50 > 0
    assert snap.atr > 0
    assert snap.volume_mean_24h > 0


def test_compute_raises_on_insufficient_data():
    engine = IndicatorEngine()
    df = _make_ohlcv(10)
    import pytest
    with pytest.raises(ValueError):
        engine.compute("BTC/USDT", df)
