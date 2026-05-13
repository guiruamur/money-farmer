from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage
from tests.fakes.market import FakeMarketDataSource


def _signal(action: SignalAction = SignalAction.BUY) -> Signal:
    return Signal(
        action=action, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_schedule_creates_jobs_at_correct_due_times(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )

    market = FakeMarketDataSource(
        tickers={"BTC/USDT": (100.0, datetime.now(timezone.utc))}
    )
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    now = datetime.now(timezone.utc)
    svc.schedule_measurements(signal_id=sig_id, generated_at=now)

    jobs = storage.list_due_outcome_jobs(now=now + timedelta(hours=25))
    horizons = sorted([j["horizon"] for j in jobs])
    assert horizons == ["1h", "24h", "4h"]


def test_run_due_jobs_measures_and_saves_outcome(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(
        tickers={"BTC/USDT": (105.0, now)}
    )
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="1h", due_at=now)

    svc.run_due_jobs(now=now + timedelta(seconds=1))

    outcomes = storage.list_outcomes_for_signal(sig_id)
    assert len(outcomes) == 1
    assert outcomes[0]["horizon"] == "1h"
    assert outcomes[0]["return_pct"] == 5.0
    assert outcomes[0]["verdict"] == "correct"  # BUY y subió → correct


def test_verdict_for_sell_signal(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(action=SignalAction.SELL), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(tickers={"BTC/USDT": (95.0, now)})
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[1, 4, 24], memory=None,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    svc.run_due_jobs(now=now + timedelta(seconds=1))

    outcomes = storage.list_outcomes_for_signal(sig_id)
    # SELL y bajó → correct
    assert outcomes[0]["verdict"] == "correct"
    assert outcomes[0]["return_pct"] == pytest.approx(-5.0)


def test_measure_calls_memory_update_outcome_for_4h(tmp_path: Path):
    """_measure must call memory.update_outcome with return_4h when horizon is 4h."""
    from tests.fakes.memory import InMemoryMemory

    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    # Simulate memory.add having been called and entry_id persisted
    memory = InMemoryMemory()
    mem_eid = memory.add(embedding=[1.0], text="sit", metadata={"pair": "BTC/USDT"})
    storage.update_signal_memory_entry_id(signal_id=sig_id, memory_entry_id=mem_eid)

    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(tickers={"BTC/USDT": (110.0, now)})
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[4], memory=memory,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    svc.run_due_jobs(now=now + timedelta(seconds=1))

    # Outcome stored in SQLite
    outcomes = storage.list_outcomes_for_signal(sig_id)
    assert len(outcomes) == 1
    assert outcomes[0]["return_pct"] == pytest.approx(10.0)

    # Memory updated with return_4h
    hits = memory.search(embedding=[1.0], k=1)
    assert hits[0].metadata.get("return_4h") == pytest.approx(10.0)
    assert "return_24h" not in hits[0].metadata


def test_measure_calls_memory_update_outcome_for_24h(tmp_path: Path):
    """_measure must call memory.update_outcome with return_24h when horizon is 24h."""
    from tests.fakes.memory import InMemoryMemory

    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    memory = InMemoryMemory()
    mem_eid = memory.add(embedding=[1.0], text="sit", metadata={"pair": "BTC/USDT"})
    storage.update_signal_memory_entry_id(signal_id=sig_id, memory_entry_id=mem_eid)

    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(tickers={"BTC/USDT": (90.0, now)})
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[24], memory=memory,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="24h", due_at=now)
    svc.run_due_jobs(now=now + timedelta(seconds=1))

    hits = memory.search(embedding=[1.0], k=1)
    assert hits[0].metadata.get("return_24h") == pytest.approx(-10.0)
    assert "return_4h" not in hits[0].metadata


def test_measure_skips_memory_update_when_no_entry_id(tmp_path: Path):
    """If a signal has no memory_entry_id, memory.update_outcome must not be called."""
    from tests.fakes.memory import InMemoryMemory

    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    # No memory_entry_id set on this signal

    memory = InMemoryMemory()
    mem_eid = memory.add(embedding=[1.0], text="sit", metadata={"pair": "BTC/USDT"})

    now = datetime.now(timezone.utc)
    market = FakeMarketDataSource(tickers={"BTC/USDT": (105.0, now)})
    svc = OutcomeService(
        storage=storage, market=market, horizons_hours=[4], memory=memory,
    )
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    svc.run_due_jobs(now=now + timedelta(seconds=1))

    # Memory entry must be untouched
    hits = memory.search(embedding=[1.0], k=1)
    assert "return_4h" not in hits[0].metadata
