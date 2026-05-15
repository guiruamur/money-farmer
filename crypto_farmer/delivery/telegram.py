"""Synchronous Telegram notifier.

Sends messages by hitting the Bot HTTP API directly with httpx (no asyncio).
We used to call python-telegram-bot's async Bot.send_message wrapped in
asyncio.run, but that broke when two `asyncio.run` calls happened back-to-back
in the same scheduler thread (the Bot's internal async client was bound to the
first event loop, which was already closed by the time the second call ran).

The polling side (Application.updater.start_polling) keeps using
python-telegram-bot in __main__.py; this notifier is only for outbound calls
from synchronous scheduler threads.
"""

from __future__ import annotations

from html import escape
from typing import Any

import httpx

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.paper.models import ActionKind, ActionOutcome
from crypto_farmer.signals.models import CycleStatus


_ACTION_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}


def _extract_token(bot_or_token: Any) -> str:
    # Backwards-compat: accept either a string token or a python-telegram-bot Bot.
    if isinstance(bot_or_token, str):
        return bot_or_token
    if hasattr(bot_or_token, "token"):
        return bot_or_token.token
    raise TypeError("bot must be a python-telegram-bot Bot or a token string")


def format_signal_message(ds: DeliverableSignal) -> str:
    s = ds.signal
    emoji = _ACTION_EMOJI.get(s.action.value, "")
    pair = escape(ds.pair)
    reasoning = escape(s.reasoning)
    factors = ", ".join(escape(f) for f in s.key_factors)
    lines = [
        f"{emoji} <b>{s.action.value}</b> {pair} (conf {s.confidence})",
        f"Precio: {ds.price_at_signal:.4f}",
    ]
    if s.entry_price_hint is not None:
        lines.append(f"Entrada sugerida: {s.entry_price_hint:.4f}")
    if s.invalidation_level is not None:
        lines.append(f"Invalidación: {s.invalidation_level:.4f}")
    lines.append(f"Horizonte: {s.time_horizon.value}")
    lines.append(f"Razón: {reasoning}")
    if s.key_factors:
        lines.append("Factores: " + factors)
    return "\n".join(lines)


def format_paper_outcome(outcome: ActionOutcome) -> str | None:
    pair = escape(outcome.pair)
    if outcome.kind == ActionKind.OPENED and outcome.position is not None:
        p = outcome.position
        return (
            f"📥 <b>Paper BUY</b> {pair}\n"
            f"Cantidad: {p.qty:.6f}  ·  Entrada: {p.avg_entry_price:.4f}"
        )
    if outcome.kind == ActionKind.CLOSED and outcome.trade is not None:
        t = outcome.trade
        emoji = "✅" if t.net_profit > 0 else "🔻" if t.net_profit < 0 else "⚪"
        lines = [
            f"{emoji} <b>Paper SELL</b> {pair}",
            f"Cantidad: {t.qty:.6f}  ·  Salida: {t.exit_price:.4f}",
            f"P&amp;L neto: {t.net_profit:+.2f}€ ({t.return_pct:+.2f}%)",
        ]
        if t.to_vault > 0:
            lines.append(f"🏦 A caja fuerte: {t.to_vault:.2f}€")
        if outcome.bankruptcy:
            lines.append("")
            lines.append("💀 <b>BANCARROTA</b> — la IA fundió el capital.")
            lines.append("Mi reproche: BUYs sin criterio, drawdown sin control.")
            lines.append("Recargando 1000€ frescos (la caja fuerte queda intacta).")
        return "\n".join(lines)
    if outcome.kind == ActionKind.IGNORED_NO_POS:
        return (
            f"ℹ️ Señal <b>SELL</b> de {pair} ignorada (no hay posición abierta)."
        )
    return None


class TelegramNotifier:
    """Synchronous Telegram client. Accepts a Bot instance or a raw token."""

    def __init__(self, *, bot: Any, chat_id: str, timeout: float = 10.0) -> None:
        self._token = _extract_token(bot)
        self._chat_id = chat_id
        self._client = httpx.Client(timeout=timeout)
        # Keep a reference to the Bot for tests that introspect it (legacy API).
        self._bot = bot

    def _send(self, text: str, *, parse_mode: str | None = "HTML") -> None:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": self._chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            r = self._client.post(url, data=payload)
            r.raise_for_status()
        except Exception:
            # Outbound notifications are best-effort: a Telegram glitch must
            # never crash a trading cycle.
            pass

    def send_text(self, text: str) -> None:
        """Send a free-form HTML message (system events, etc.). Best-effort."""
        self._send(text)

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        for ds in signals:
            self._send(format_signal_message(ds))

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        if status == CycleStatus.OK:
            return
        prefix = "⚠️" if status == CycleStatus.DEGRADED else "⛔"
        text = f"{prefix} Ciclo {escape(status.value)}"
        if note:
            text += f": {escape(note)}"
        self._send(text)

    def deliver_paper_outcome(self, outcome: ActionOutcome) -> None:
        text = format_paper_outcome(outcome)
        if text is None:
            return
        self._send(text)
