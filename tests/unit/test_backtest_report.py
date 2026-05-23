from datetime import datetime, timezone

from crypto_farmer.backtest.report import build_report
from crypto_farmer.storage.db import Storage
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon


def _sig(action):
    return Signal(action=action, confidence=70, reasoning="r",
                  entry_price_hint=None, invalidation_level=None,
                  time_horizon=TimeHorizon.SHORT, key_factors=[])


def test_report_counts_signals_and_winrate(tmp_path):
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    cid = s.start_cycle()
    sid = s.save_signal(cycle_id=cid, pair="BTC/USDT", timeframe="15m",
                        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True)
    s.save_outcome(signal_id=sid, horizon="4h", measured_at=t,
                   price_then=105.0, return_pct=5.0, verdict="correct")

    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 1" in text
    assert "BUY" in text
    assert "4h: 100% (1/1)" in text


def test_report_handles_empty(tmp_path):
    t = datetime(2026, 5, 17, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 0" in text
