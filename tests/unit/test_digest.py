from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from crypto_farmer.delivery.digest import DigestSender, build_digest_text
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)
from crypto_farmer.storage.db import Storage


def _sig(action: SignalAction = SignalAction.BUY) -> Signal:
    return Signal(
        action=action, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_build_digest_with_no_activity(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    text = build_digest_text(storage=storage, lookback_hours=1)
    assert "Ciclos: 0" in text
    assert "Señales: 0" in text
    assert "Win rate 1h: —" in text


def test_build_digest_counts_recent_only(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    # Note: started_at is auto-stamped to "now"; we can't easily fake old cycles
    # without monkeypatching. Instead we use the lookback to capture "very recent".
    cycle = storage.start_cycle()
    storage.finish_cycle(
        cycle, status=CycleStatus.OK,
        pairs_analyzed=5, pairs_passed_prefilter=2,
        signals_generated=1, notes=None,
    )
    sig_id = storage.save_signal(
        cycle_id=cycle, pair="BTC/USDT", timeframe="15m",
        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True,
    )
    storage.save_outcome(
        signal_id=sig_id, horizon="4h", measured_at=datetime.now(timezone.utc),
        price_then=105.0, return_pct=5.0, verdict="correct",
    )

    text = build_digest_text(storage=storage, lookback_hours=1, memory_count=42)
    assert "Ciclos: 1 (ok 1" in text
    assert "Señales: 1" in text
    assert "BUY=1" in text
    assert "4h: 100% (1/1)" in text
    assert "Memoria RAG: 42 situaciones" in text
    assert "Mejor: BTC/USDT BUY +5.00%" in text


def test_digest_lookback_excludes_old(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle = storage.start_cycle()
    storage.finish_cycle(
        cycle, status=CycleStatus.OK,
        pairs_analyzed=0, pairs_passed_prefilter=0,
        signals_generated=0, notes=None,
    )
    # lookback in the past — captures nothing because cycle is "now"
    far_future = datetime.now(timezone.utc) + timedelta(days=2)
    text = build_digest_text(storage=storage, lookback_hours=0.0001, now=far_future)
    assert "Ciclos: 0" in text


def test_digest_sender_calls_bot(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    bot = MagicMock()
    bot.send_message = AsyncMock()
    sender = DigestSender(
        storage=storage, bot=bot, chat_id="42",
        lookback_hours=1, memory_count_fn=lambda: 7,
    )
    sender.send()
    bot.send_message.assert_awaited()
    _, kwargs = bot.send_message.await_args
    assert kwargs["chat_id"] == "42"
    assert kwargs["parse_mode"] == "HTML"
    assert "Memoria RAG: 7 situaciones" in kwargs["text"]


def test_digest_sender_swallows_bot_errors(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("boom"))
    sender = DigestSender(
        storage=storage, bot=bot, chat_id="42",
        lookback_hours=1, memory_count_fn=None,
    )
    # Should not raise — failed digest is best-effort
    sender.send()
