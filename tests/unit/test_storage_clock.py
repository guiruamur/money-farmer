from datetime import datetime, timezone

from crypto_farmer.storage.db import Storage
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon


class _FrozenClock:
    def __init__(self, t): self._t = t
    def now(self): return self._t


def _sig():
    return Signal(
        action=SignalAction.BUY, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_storage_uses_injected_clock_for_signal_timestamp(tmp_path):
    frozen = datetime(2026, 5, 17, 9, 30, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "t.db", clock=_FrozenClock(frozen))
    cid = s.start_cycle()
    sid = s.save_signal(
        cycle_id=cid, pair="BTC/USDT", timeframe="15m",
        signal=_sig(), price_at_signal=100.0, delivered=False,
    )
    row = s.get_signal_by_id(signal_id=sid)
    assert row["generated_at"].startswith("2026-05-17T09:30:00")


def test_storage_defaults_to_system_clock(tmp_path):
    s = Storage(db_path=tmp_path / "t.db")
    cid = s.start_cycle()
    rows = s.list_recent_cycles(limit=1)
    assert rows and rows[0]["id"] == cid
