from pathlib import Path

from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.signals.models import (
    Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage


def _sig(action: SignalAction) -> Signal:
    return Signal(
        action=action, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_feedback_with_no_signals(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    fb = FeedbackBuilder(storage=storage)
    out = fb.build(lookback=20)
    assert out["lookback"] == 20
    assert out["win_rate"] == 0
    assert "sin histórico" in out["summary"].lower()


def test_feedback_computes_win_rate(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle = storage.start_cycle()
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)

    s1 = storage.save_signal(
        cycle_id=cycle, pair="BTC/USDT", timeframe="15m",
        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True,
    )
    s2 = storage.save_signal(
        cycle_id=cycle, pair="ETH/USDT", timeframe="15m",
        signal=_sig(SignalAction.SELL), price_at_signal=2000.0, delivered=True,
    )
    storage.save_outcome(
        signal_id=s1, horizon="4h", measured_at=now,
        price_then=105.0, return_pct=5.0, verdict="correct",
    )
    storage.save_outcome(
        signal_id=s2, horizon="4h", measured_at=now,
        price_then=2050.0, return_pct=2.5, verdict="incorrect",
    )

    fb = FeedbackBuilder(storage=storage)
    out = fb.build(lookback=10)
    assert out["win_rate"] == 50
    assert "BTC/USDT" in out["summary"]
