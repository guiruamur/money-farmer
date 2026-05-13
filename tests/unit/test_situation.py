from datetime import datetime, timezone

from crypto_farmer.learning.situation import Situation
from crypto_farmer.signals.models import IndicatorSnapshot


def _snap(**kw) -> IndicatorSnapshot:
    base = dict(
        pair="BTC/USDT", timestamp=datetime(2026, 5, 12, 10, tzinfo=timezone.utc),
        rsi=28.5, macd=1.0, macd_signal=0.5, macd_hist=0.5,
        ema_20=100.0, ema_50=99.0, bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0, volume=120.0, volume_mean_24h=100.0,
    )
    base.update(kw)
    return IndicatorSnapshot(**base)


def test_situation_text_contains_key_info():
    s = Situation.from_snapshot(_snap())
    txt = s.as_text()
    assert "BTC/USDT" in txt
    assert "RSI 28.5" in txt
    assert "ATR" in txt
    assert "MACD" in txt


def test_situation_summary_short():
    s = Situation.from_snapshot(_snap(rsi=72))
    summary = s.short_summary()
    assert len(summary) <= 200
    assert "sobrecompra" in summary.lower() or "rsi" in summary.lower()
