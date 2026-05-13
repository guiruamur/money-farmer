from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.delivery.bot_commands import (
    CommandContext, BotCommands, format_status, format_last_signals,
)
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon
from crypto_farmer.storage.db import Storage


def _ctx(tmp_path: Path) -> CommandContext:
    storage = Storage(db_path=tmp_path / "t.db")
    return CommandContext(
        storage=storage,
        scheduler_paused_getter=lambda: False,
        scheduler_pauser=lambda: None,
        scheduler_resumer=lambda: None,
        health_checker=lambda: {"ollama": "ok", "binance": "ok", "chromadb": "ok"},
        config_snapshot={"scheduler": {"interval_minutes": 15}, "market": {"pairs": ["BTC/USDT"]}},
    )


def test_status_with_no_cycles(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).status()
    assert "ciclos" in msg.lower()
    assert "0" in msg


def test_last_with_no_signals(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).last()
    assert "sin se" in msg.lower() or "ninguna" in msg.lower()


def test_pause_and_resume(tmp_path: Path):
    state = {"paused": False}
    ctx = _ctx(tmp_path)
    ctx = CommandContext(
        storage=ctx.storage,
        scheduler_paused_getter=lambda: state["paused"],
        scheduler_pauser=lambda: state.update({"paused": True}),
        scheduler_resumer=lambda: state.update({"paused": False}),
        health_checker=ctx.health_checker,
        config_snapshot=ctx.config_snapshot,
    )
    cmd = BotCommands(ctx)
    msg = cmd.pause()
    assert state["paused"]
    assert "pausa" in msg.lower()
    msg = cmd.resume()
    assert not state["paused"]
    assert "reanud" in msg.lower()


def test_health(tmp_path: Path):
    ctx = _ctx(tmp_path)
    msg = BotCommands(ctx).health()
    assert "ollama" in msg.lower()
    assert "ok" in msg.lower()


def test_config_redacts_secrets(tmp_path: Path):
    ctx = _ctx(tmp_path)
    ctx = CommandContext(
        storage=ctx.storage,
        scheduler_paused_getter=ctx.scheduler_paused_getter,
        scheduler_pauser=ctx.scheduler_pauser,
        scheduler_resumer=ctx.scheduler_resumer,
        health_checker=ctx.health_checker,
        config_snapshot={
            "delivery": {"telegram": {"bot_token": "SECRET", "chat_id": "42"}},
            "news_credentials": {"cryptopanic_token": "SECRET2"},
            "scheduler": {"interval_minutes": 15},
        },
    )
    msg = BotCommands(ctx).config()
    assert "SECRET" not in msg
    assert "SECRET2" not in msg
    assert "***" in msg
