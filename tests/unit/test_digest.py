from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import respx

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


def test_digest_flags_crashed_cycles(tmp_path: Path):
    """A cycle started but never finished (status NULL) must show as crashed + alert."""
    storage = Storage(db_path=tmp_path / "t.db")
    # 1 healthy cycle
    ok_cycle = storage.start_cycle()
    storage.finish_cycle(
        ok_cycle, status=CycleStatus.OK,
        pairs_analyzed=5, pairs_passed_prefilter=0,
        signals_generated=0, notes=None,
    )
    # 2 crashed cycles: started but never finished (no status)
    storage.start_cycle()
    storage.start_cycle()

    text = build_digest_text(storage=storage, lookback_hours=1)
    assert "crasheados 2" in text
    assert "🚨" in text
    assert "ALERTA" in text


def test_digest_no_alert_when_all_ok(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    cycle = storage.start_cycle()
    storage.finish_cycle(
        cycle, status=CycleStatus.OK,
        pairs_analyzed=5, pairs_passed_prefilter=0,
        signals_generated=0, notes=None,
    )
    text = build_digest_text(storage=storage, lookback_hours=1)
    assert "🚨" not in text
    assert "crasheados" not in text


def test_digest_winrate_counts_outcomes_measured_in_window(tmp_path: Path):
    """Outcomes whose measurement landed inside the digest window must count,
    even if the signal itself is older than the window.

    Realistic scenario: digest runs every 30 min with lookback=30min. A 4h
    outcome for a signal generated 4h ago is measured "now" — the signal is
    outside the 30-min window but the outcome is fresh. The digest must
    surface that win-rate; otherwise it always shows "—" for 1h/4h/24h.
    """
    import sqlite3
    storage = Storage(db_path=tmp_path / "t.db")
    cycle = storage.start_cycle()
    storage.finish_cycle(
        cycle, status=CycleStatus.OK,
        pairs_analyzed=0, pairs_passed_prefilter=0,
        signals_generated=0, notes=None,
    )
    # Insert a 5h-old signal directly so we can control generated_at
    # (Storage.save_signal auto-stamps "now").
    now = datetime.now(timezone.utc)
    old_generated = (now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with sqlite3.connect(tmp_path / "t.db") as con:
        cur = con.execute(
            "INSERT INTO signals (cycle_id, pair, timeframe, generated_at, action, "
            "confidence, reasoning, key_factors_json, delivered, price_at_signal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cycle, "ETH/USDT", "15m", old_generated, "BUY",
             70, "r", "[]", 1, 100.0),
        )
        sig_id = cur.lastrowid
        con.commit()
    # Outcome was measured a minute ago — well inside any reasonable digest window.
    storage.save_outcome(
        signal_id=sig_id, horizon="4h", measured_at=now - timedelta(minutes=1),
        price_then=103.0, return_pct=3.0, verdict="correct",
    )

    # Digest now with lookback 30 min: the signal (5h ago) is OUTSIDE; the
    # outcome (1 min ago) is INSIDE. The current implementation iterates
    # recent_signals and would miss this — that's the bug we're fixing.
    text = build_digest_text(storage=storage, lookback_hours=0.5, now=now)
    assert "4h: 100% (1/1)" in text
    assert "Mejor: ETH/USDT BUY +3.00%" in text


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


_DIGEST_URL = "https://api.telegram.org/botTOK/sendMessage"


@respx.mock
def test_digest_sender_posts_to_bot_api(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    route = respx.post(_DIGEST_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    sender = DigestSender(
        storage=storage, bot="TOK", chat_id="42",
        lookback_hours=1, memory_count_fn=lambda: 7,
    )
    sender.send()
    assert route.called
    payload = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert payload["chat_id"] == "42"
    assert payload["parse_mode"] == "HTML"
    assert "Memoria RAG: 7 situaciones" in payload["text"]


@respx.mock
def test_digest_sender_swallows_bot_errors(tmp_path: Path):
    storage = Storage(db_path=tmp_path / "t.db")
    respx.post(_DIGEST_URL).mock(return_value=httpx.Response(500))
    sender = DigestSender(
        storage=storage, bot="TOK", chat_id="42",
        lookback_hours=1, memory_count_fn=None,
    )
    # Should not raise — failed digest is best-effort
    sender.send()
