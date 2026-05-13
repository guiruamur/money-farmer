from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from crypto_farmer.analysis.prefilter import (
    PrefilterConfig,
    Prefilter,
    PrefilterDecision,
)
from crypto_farmer.signals.models import IndicatorSnapshot, SignalAction


def _snap(**overrides) -> IndicatorSnapshot:
    base = dict(
        pair="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        rsi=50.0, macd=0.0, macd_signal=0.0, macd_hist=0.0,
        ema_20=100.0, ema_50=100.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=10.0, atr_mean_20=10.0,
        volume=100.0, volume_mean_24h=100.0,
    )
    base.update(overrides)
    return IndicatorSnapshot(**base)


def _cfg() -> PrefilterConfig:
    return PrefilterConfig(
        rsi_oversold=30, rsi_overbought=70,
        volume_anomaly_factor=1.8, atr_expansion_factor=1.5,
        cooldown_minutes=60,
    )


def test_rsi_oversold_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=28), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "rsi_extreme" in decision.triggers


def test_rsi_overbought_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=72), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "rsi_extreme" in decision.triggers


def test_neutral_rsi_does_not_pass_alone():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(rsi=50), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert not decision.passes


def test_volume_anomaly_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(volume=200, volume_mean_24h=100), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "volume_anomaly" in decision.triggers


def test_atr_expansion_passes():
    pf = Prefilter(_cfg())
    decision = pf.evaluate(_snap(atr=20, atr_mean_20=10), recent_history=pd.DataFrame(), last_signal_for_pair=None)
    assert decision.passes
    assert "atr_expansion" in decision.triggers


def test_ema_cross_passes():
    pf = Prefilter(_cfg())
    history = pd.DataFrame([
        {"ema_20": 99.0, "ema_50": 100.0},
        {"ema_20": 99.5, "ema_50": 100.0},
        {"ema_20": 100.5, "ema_50": 100.0},
    ])
    decision = pf.evaluate(_snap(ema_20=100.5, ema_50=100.0), recent_history=history, last_signal_for_pair=None)
    assert decision.passes
    assert "ema_cross" in decision.triggers


def test_range_breakout_passes():
    pf = Prefilter(_cfg())
    history = pd.DataFrame({"high": [99.0] * 20, "low": [95.0] * 20, "close": [98.0] * 20})
    snap = _snap()
    decision = pf.evaluate(snap, recent_history=history.assign(close=[98.0]*19 + [101.0]), last_signal_for_pair=None)
    assert decision.passes
    assert "range_breakout" in decision.triggers


def test_cooldown_blocks_same_action():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    decision = pf.evaluate(
        _snap(rsi=28),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert not decision.passes
    assert decision.reason == "cooldown"


def test_cooldown_bypassed_on_direction_change():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    decision = pf.evaluate(
        _snap(rsi=72),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert decision.passes


def test_cooldown_expired_passes():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=90)
    decision = pf.evaluate(
        _snap(rsi=28),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.BUY, last_time),
    )
    assert decision.passes


def test_cooldown_does_not_apply_after_hold():
    pf = Prefilter(_cfg())
    last_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    decision = pf.evaluate(
        _snap(rsi=28),
        recent_history=pd.DataFrame(),
        last_signal_for_pair=(SignalAction.HOLD, last_time),
    )
    assert decision.passes
