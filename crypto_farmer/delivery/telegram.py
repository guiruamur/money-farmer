from __future__ import annotations

import asyncio
from html import escape

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.paper.models import ActionKind, ActionOutcome
from crypto_farmer.signals.models import CycleStatus


_ACTION_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}


def format_signal_message(ds: DeliverableSignal) -> str:
    """Render a DeliverableSignal as Telegram HTML.

    HTML mode is used (not Markdown) because Markdown trips on unmatched `*`
    or `_` in reasoning text; HTML only needs `< > &` escaped.
    """
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


class TelegramNotifier:
    def __init__(self, *, bot, chat_id: str) -> None:
        self._bot = bot
        self._chat_id = chat_id

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        for ds in signals:
            text = format_signal_message(ds)
            asyncio.run(
                self._bot.send_message(
                    chat_id=self._chat_id, text=text, parse_mode="HTML",
                )
            )

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        if status == CycleStatus.OK:
            return
        prefix = "⚠️" if status == CycleStatus.DEGRADED else "⛔"
        text = f"{prefix} Ciclo {escape(status.value)}"
        if note:
            text += f": {escape(note)}"
        asyncio.run(
            self._bot.send_message(chat_id=self._chat_id, text=text)
        )

    def deliver_paper_outcome(self, outcome: ActionOutcome) -> None:
        """Notify about a paper-trading action. Silent for HOLD/has-pos cases."""
        text = format_paper_outcome(outcome)
        if text is None:
            return
        try:
            asyncio.run(
                self._bot.send_message(
                    chat_id=self._chat_id, text=text, parse_mode="HTML",
                )
            )
        except Exception:
            # Best-effort: don't crash the cycle on a Telegram glitch.
            pass


def format_paper_outcome(outcome: ActionOutcome) -> str | None:
    """Render a paper-trading outcome as Telegram HTML. Returns None to skip."""
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
            f"ℹ️ Señal <b>SELL</b> de {pair} ignorada (no hay posición abierta de este par)."
        )
    # IGNORED_HAS_POS, IGNORED_NO_CASH, IGNORED_HOLD: silenciosos
    return None
