from unittest.mock import AsyncMock, MagicMock

import pytest

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.delivery.telegram import TelegramNotifier, format_signal_message
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)


def _ds(action: SignalAction = SignalAction.BUY, conf: int = 70) -> DeliverableSignal:
    return DeliverableSignal(
        pair="BTC/USDT",
        signal=Signal(
            action=action, confidence=conf, reasoning="RSI sobreventa",
            entry_price_hint=100.0, invalidation_level=95.0,
            time_horizon=TimeHorizon.SHORT, key_factors=["rsi"],
        ),
        price_at_signal=100.0,
    )


def test_format_signal_message_buy():
    text = format_signal_message(_ds(SignalAction.BUY, 75))
    assert "BTC/USDT" in text
    assert "BUY" in text
    assert "75" in text
    assert "RSI sobreventa" in text


def test_telegram_notifier_calls_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    n = TelegramNotifier(bot=bot, chat_id="123")
    n.deliver([_ds()])
    bot.send_message.assert_awaited()
    args, kwargs = bot.send_message.await_args
    assert kwargs["chat_id"] == "123"
    assert "BTC/USDT" in kwargs["text"]


def test_telegram_notifier_deliver_cycle_status_only_when_not_ok():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    n = TelegramNotifier(bot=bot, chat_id="123")
    n.deliver_cycle_status(status=CycleStatus.OK, note=None)
    bot.send_message.assert_not_called()

    n.deliver_cycle_status(status=CycleStatus.DEGRADED, note="news caídas")
    bot.send_message.assert_awaited()
