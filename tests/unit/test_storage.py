import json
from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.signals.models import (
    CycleStatus, NewsItem, Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage


def _signal() -> Signal:
    return Signal(
        action=SignalAction.BUY, confidence=65, reasoning="r",
        entry_price_hint=100.0, invalidation_level=95.0,
        time_horizon=TimeHorizon.SHORT, key_factors=["k1"],
    )


def test_save_cycle_and_signals(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    storage.finish_cycle(
        cycle_id, status=CycleStatus.OK,
        pairs_analyzed=10, pairs_passed_prefilter=2,
        signals_generated=2, notes=None,
    )
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.5, delivered=True,
    )

    cycles = storage.list_recent_cycles(limit=5)
    assert len(cycles) == 1
    assert cycles[0]["status"] == CycleStatus.OK.value

    signals = storage.list_recent_signals(limit=5)
    assert len(signals) == 1
    assert signals[0]["id"] == sig_id
    assert signals[0]["pair"] == "BTC/USDT"

    got = storage.get_signal_by_id(signal_id=sig_id)
    assert got is not None and got["id"] == sig_id
    assert storage.get_signal_by_id(signal_id=9999) is None


def test_save_outcome(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    storage.save_outcome(
        signal_id=sig_id, horizon="4h",
        measured_at=datetime.now(timezone.utc),
        price_then=105.0, return_pct=5.0, verdict="correct",
    )

    outcomes = storage.list_outcomes_for_signal(sig_id)
    assert len(outcomes) == 1
    assert outcomes[0]["return_pct"] == 5.0


def test_news_cache_unique_url(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    item = NewsItem(
        source="x", url="https://u/1", title="t", body=None,
        published_at=datetime.now(timezone.utc), related_pairs=["BTC/USDT"],
    )
    storage.save_news_items([item])
    storage.save_news_items([item])  # idempotente por URL UNIQUE
    rows = storage.list_news_since(since=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert len(rows) == 1


def test_save_analysis_context(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    storage.save_analysis_context(
        signal_id=sig_id,
        indicators={"rsi": 28},
        news=[],
        memory_hits=[],
        feedback_summary="ninguna",
        prompt_rendered="prompt",
        raw_llm_response='{"action": "BUY"}',
    )
    ctx = storage.get_analysis_context(sig_id)
    assert ctx is not None
    assert json.loads(ctx["indicators_json"]) == {"rsi": 28}


def test_pending_outcome_jobs(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    now = datetime.now(timezone.utc)
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="1h", due_at=now)
    storage.enqueue_outcome_job(signal_id=sig_id, horizon="4h", due_at=now)
    due = storage.list_due_outcome_jobs(now=now)
    assert len(due) == 2
    storage.mark_outcome_job_done(job_id=due[0]["id"])
    due_after = storage.list_due_outcome_jobs(now=now)
    assert len(due_after) == 1


def test_memory_entry_id_roundtrip(tmp_path: Path):
    """memory_entry_id is NULL on creation and can be set via update_signal_memory_entry_id."""
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_id = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    # Freshly saved signal has no memory_entry_id
    row = storage.get_signal_by_id(signal_id=sig_id)
    assert row is not None
    assert row.get("memory_entry_id") is None

    # Set it and confirm it persists
    storage.update_signal_memory_entry_id(signal_id=sig_id, memory_entry_id="sit_42")
    row = storage.get_signal_by_id(signal_id=sig_id)
    assert row is not None
    assert row["memory_entry_id"] == "sit_42"


def test_update_signal_memory_entry_id_does_not_affect_other_signals(tmp_path: Path):
    """Updating memory_entry_id for one signal must not affect siblings."""
    storage = Storage(db_path=tmp_path / "t.db")
    cycle_id = storage.start_cycle()
    sig_a = storage.save_signal(
        cycle_id=cycle_id, pair="BTC/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=100.0, delivered=True,
    )
    sig_b = storage.save_signal(
        cycle_id=cycle_id, pair="ETH/USDT", timeframe="15m",
        signal=_signal(), price_at_signal=2000.0, delivered=False,
    )
    storage.update_signal_memory_entry_id(signal_id=sig_a, memory_entry_id="sit_1")

    row_a = storage.get_signal_by_id(signal_id=sig_a)
    row_b = storage.get_signal_by_id(signal_id=sig_b)
    assert row_a is not None and row_a["memory_entry_id"] == "sit_1"
    assert row_b is not None and row_b.get("memory_entry_id") is None
