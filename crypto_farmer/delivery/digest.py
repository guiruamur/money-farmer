"""Periodic Telegram digest summarising recent cycles, signals and outcomes.

Used for high-frequency follow-up during validation. Not enabled in tests; the
scheduler skips wiring it if `digest_minutes` is 0 or `digest_callable` is None.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Callable

from crypto_farmer.logging_setup import get_logger
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_digest_text(
    *,
    storage: Storage,
    lookback_hours: float,
    memory_count: int | None = None,
    now: datetime | None = None,
) -> str:
    """Render an HTML-formatted summary of activity in the last `lookback_hours`."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=lookback_hours)

    # Cycles
    all_cycles = storage.list_recent_cycles(limit=500)
    recent_cycles = [
        c for c in all_cycles
        if (ts := _parse_ts(c.get("started_at"))) and ts >= since
    ]
    ok = sum(1 for c in recent_cycles if c.get("status") == "ok")
    degraded = sum(1 for c in recent_cycles if c.get("status") == "degraded")
    failed = sum(1 for c in recent_cycles if c.get("status") == "failed")

    # Signals
    all_signals = storage.list_recent_signals(limit=500)
    recent_signals = [
        s for s in all_signals
        if (ts := _parse_ts(s.get("generated_at"))) and ts >= since
    ]
    actions: dict[str, int] = {}
    delivered = 0
    for s in recent_signals:
        actions[s["action"]] = actions.get(s["action"], 0) + 1
        if s.get("delivered"):
            delivered += 1

    # Outcomes by horizon
    wins_by_h: dict[str, int] = {"1h": 0, "4h": 0, "24h": 0}
    rated_by_h: dict[str, int] = {"1h": 0, "4h": 0, "24h": 0}
    best: tuple[str, str, float] | None = None  # (pair, action, return)
    worst: tuple[str, str, float] | None = None
    for s in recent_signals:
        outcomes = storage.list_outcomes_for_signal(s["id"])
        for o in outcomes:
            h = o["horizon"]
            if h not in rated_by_h:
                continue
            rated_by_h[h] += 1
            if o.get("verdict") == "correct":
                wins_by_h[h] += 1
            ret = o.get("return_pct")
            if ret is not None:
                t = (s["pair"], s["action"], float(ret))
                if best is None or t[2] > best[2]:
                    best = t
                if worst is None or t[2] < worst[2]:
                    worst = t

    def wr(h: str) -> str:
        rated = rated_by_h[h]
        return f"{int(round(100 * wins_by_h[h] / rated))}% ({wins_by_h[h]}/{rated})" if rated else "—"

    dist = ", ".join(f"{a}={n}" for a, n in actions.items()) or "—"

    lines = [
        f"📊 <b>Digest</b> (últimas {lookback_hours:g}h)",
        f"Ciclos: {len(recent_cycles)} (ok {ok}, deg {degraded}, fail {failed})",
        f"Señales: {len(recent_signals)} (entregadas {delivered}). Distribución: {dist}",
        f"Win rate 1h: {wr('1h')}  ·  4h: {wr('4h')}  ·  24h: {wr('24h')}",
    ]
    if memory_count is not None:
        lines.append(f"Memoria RAG: {memory_count} situaciones")
    if best is not None:
        lines.append(f"Mejor: {escape(best[0])} {escape(best[1])} {best[2]:+.2f}%")
    if worst is not None and worst != best:
        lines.append(f"Peor: {escape(worst[0])} {escape(worst[1])} {worst[2]:+.2f}%")
    return "\n".join(lines)


class DigestSender:
    """Builds and sends a digest message via the Telegram bot."""

    def __init__(
        self,
        *,
        storage: Storage,
        bot,
        chat_id: str,
        lookback_hours: float,
        memory_count_fn: Callable[[], int] | None = None,
    ) -> None:
        self._storage = storage
        self._bot = bot
        self._chat_id = chat_id
        self._lookback_hours = lookback_hours
        self._memory_count_fn = memory_count_fn

    def send(self) -> None:
        memory_count: int | None = None
        if self._memory_count_fn is not None:
            try:
                memory_count = self._memory_count_fn()
            except Exception as e:
                log.warning("digest_memory_count_failed", extra={"error": str(e)})

        text = build_digest_text(
            storage=self._storage,
            lookback_hours=self._lookback_hours,
            memory_count=memory_count,
        )
        try:
            asyncio.run(
                self._bot.send_message(
                    chat_id=self._chat_id, text=text, parse_mode="HTML",
                )
            )
            log.info("digest_sent", extra={"lookback_hours": self._lookback_hours})
        except Exception as e:
            log.warning("digest_send_failed", extra={"error": str(e)})
