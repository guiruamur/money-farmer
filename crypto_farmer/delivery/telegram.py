from __future__ import annotations

import asyncio

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import CycleStatus


_ACTION_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}


def format_signal_message(ds: DeliverableSignal) -> str:
    s = ds.signal
    emoji = _ACTION_EMOJI.get(s.action.value, "")
    lines = [
        f"{emoji} *{s.action.value}* {ds.pair} (conf {s.confidence})",
        f"Precio: {ds.price_at_signal:.4f}",
    ]
    if s.entry_price_hint is not None:
        lines.append(f"Entrada sugerida: {s.entry_price_hint:.4f}")
    if s.invalidation_level is not None:
        lines.append(f"Invalidación: {s.invalidation_level:.4f}")
    lines.append(f"Horizonte: {s.time_horizon.value}")
    lines.append(f"Razón: {s.reasoning}")
    if s.key_factors:
        lines.append("Factores: " + ", ".join(s.key_factors))
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
                    chat_id=self._chat_id, text=text, parse_mode="Markdown",
                )
            )

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        if status == CycleStatus.OK:
            return
        prefix = "⚠️" if status == CycleStatus.DEGRADED else "⛔"
        text = f"{prefix} Ciclo {status.value}"
        if note:
            text += f": {note}"
        asyncio.run(
            self._bot.send_message(chat_id=self._chat_id, text=text)
        )
