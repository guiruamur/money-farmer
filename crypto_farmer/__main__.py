from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load .env at the earliest possible moment so config.py sees TELEGRAM_*, etc.
load_dotenv()

from crypto_farmer.app import build_app  # noqa: E402
from crypto_farmer.logging_setup import get_logger  # noqa: E402


log = get_logger(__name__)


def _build_telegram_app(app, token: str) -> Application:
    tg = Application.builder().token(token).build()

    async def _wrap(handler_fn, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            text = handler_fn()
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")
        except Exception as e:
            log.exception("bot_command_error")
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {e}")

    async def _pair(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        pair = " ".join(ctx.args).strip().upper() if ctx.args else ""
        if not pair:
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text="Uso: /pair BTC/USDT")
            return
        text = app.bot_commands.pair(pair)
        await ctx.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")

    def _make_handler(fn):
        async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
            await _wrap(fn, update, ctx)
        return _h

    handlers = {
        "status": app.bot_commands.status,
        "last": app.bot_commands.last,
        "stats": app.bot_commands.stats,
        "pause": app.bot_commands.pause,
        "resume": app.bot_commands.resume,
        "health": app.bot_commands.health,
        "config": app.bot_commands.config,
    }
    for name, fn in handlers.items():
        tg.add_handler(CommandHandler(name, _make_handler(fn)))
    tg.add_handler(CommandHandler("pair", _pair))
    return tg


def main() -> None:
    parser = argparse.ArgumentParser(prog="crypto-farmer")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--run-once", action="store_true",
                        help="Ejecuta UN ciclo y sale (smoke test).")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print(f"Config no encontrada en {args.config}", file=sys.stderr)
        sys.exit(2)

    app = build_app(config_path=args.config)
    log.info("app_built")

    if args.run_once:
        result = app.cycle.run()
        log.info("run_once_finished", extra={"status": result.status.value})
        return

    app.scheduler.start()

    tg_app = _build_telegram_app(app, token=app.config.delivery.telegram.bot_token)

    stop_event = asyncio.Event()
    def _shutdown(*_):
        log.info("shutdown_signal")
        stop_event.set()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    async def _run() -> None:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()
        await stop_event.wait()
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()

    try:
        asyncio.run(_run())
    finally:
        app.scheduler.stop()


if __name__ == "__main__":
    main()
