import httpx
import respx

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.delivery.telegram import (
    TelegramNotifier, format_paper_outcome, format_signal_message,
)
from crypto_farmer.paper.models import ActionKind, ActionOutcome, Position, TradeResult
from crypto_farmer.signals.models import (
    CycleStatus, Signal, SignalAction, TimeHorizon,
)
from datetime import datetime, timezone


_TOKEN = "TEST_TOKEN"
_URL = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"


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


@respx.mock
def test_telegram_notifier_posts_to_bot_api():
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    n = TelegramNotifier(bot=_TOKEN, chat_id="123")
    n.deliver([_ds()])
    assert route.called
    payload = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert payload["chat_id"] == "123"
    assert "BTC/USDT" in payload["text"]
    assert payload["parse_mode"] == "HTML"


@respx.mock
def test_telegram_notifier_deliver_cycle_status_skips_ok():
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    n = TelegramNotifier(bot=_TOKEN, chat_id="123")

    n.deliver_cycle_status(status=CycleStatus.OK, note=None)
    assert not route.called

    n.deliver_cycle_status(status=CycleStatus.DEGRADED, note="news caídas")
    assert route.called


@respx.mock
def test_telegram_notifier_swallows_http_errors():
    respx.post(_URL).mock(return_value=httpx.Response(500))
    n = TelegramNotifier(bot=_TOKEN, chat_id="123")
    # Must NOT raise — outbound notifications are best-effort
    n.deliver([_ds()])


@respx.mock
def test_telegram_notifier_paper_open():
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    n = TelegramNotifier(bot=_TOKEN, chat_id="42")
    outcome = ActionOutcome(
        kind=ActionKind.OPENED, pair="SOL/USDT",
        position=Position(
            pair="SOL/USDT", qty=2.5, avg_entry_price=90.0,
            opened_at=datetime.now(timezone.utc),
        ),
    )
    n.deliver_paper_outcome(outcome)
    assert route.called
    payload = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert "Paper BUY" in payload["text"]
    assert "SOL/USDT" in payload["text"]


@respx.mock
def test_telegram_notifier_paper_close_with_vault():
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    n = TelegramNotifier(bot=_TOKEN, chat_id="42")
    now = datetime.now(timezone.utc)
    outcome = ActionOutcome(
        kind=ActionKind.CLOSED, pair="SOL/USDT",
        trade=TradeResult(
            pair="SOL/USDT", qty=2.5, entry_price=90.0, exit_price=100.0,
            gross_profit=25.0, fees=0.5, net_profit=24.5, to_vault=4.9,
            opened_at=now, closed_at=now,
        ),
    )
    n.deliver_paper_outcome(outcome)
    payload = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert "Paper SELL" in payload["text"]
    assert "+24.50€" in payload["text"]
    assert "caja fuerte" in payload["text"]


def test_format_paper_outcome_ignored_silent_cases():
    # ActionKind.IGNORED_HAS_POS / NO_CASH / HOLD -> None (no message)
    for kind in (
        ActionKind.IGNORED_HAS_POS, ActionKind.IGNORED_NO_CASH, ActionKind.IGNORED_HOLD,
    ):
        out = ActionOutcome(kind=kind, pair="X/USDT")
        assert format_paper_outcome(out) is None


def test_format_paper_outcome_ignored_no_pos_visible():
    out = ActionOutcome(kind=ActionKind.IGNORED_NO_POS, pair="X/USDT")
    text = format_paper_outcome(out)
    assert text is not None
    assert "ignorada" in text
