from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load .env at the earliest possible moment so config.py sees TELEGRAM_*, etc.
load_dotenv()

from crypto_farmer.app import build_app  # noqa: E402
from crypto_farmer.logging_setup import get_logger  # noqa: E402


log = get_logger(__name__)


def _parse_backtest_args(argv):
    import argparse
    import datetime as _dt
    p = argparse.ArgumentParser(prog="crypto-farmer backtest")
    p.add_argument("--from", dest="date_from", required=True,
                   type=lambda s: _dt.datetime.fromisoformat(s))
    p.add_argument("--to", dest="date_to", required=True,
                   type=lambda s: _dt.datetime.fromisoformat(s))
    p.add_argument("--pairs", default=None,
                   type=lambda s: [x.strip() for x in s.split(",")])
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--export-rag", action="store_true")
    return p.parse_args(argv)


def _run_backtest(argv) -> None:
    ns = _parse_backtest_args(argv)

    from crypto_farmer.config import load_config
    cfg = load_config(ns.config)

    pairs = ns.pairs or cfg.market.pairs

    run_id = (
        f"{ns.date_from:%Y%m%d}_{ns.date_to:%Y%m%d}"
        f"__{datetime.now():%Y%m%d-%H%M%S}"
    )
    run_dir = Path("data/backtest") / run_id

    from crypto_farmer.backtest.runner import build_from_config

    # Ensure since/until are timezone-aware (UTC)
    since = ns.date_from if ns.date_from.tzinfo else ns.date_from.replace(tzinfo=timezone.utc)
    until = ns.date_to if ns.date_to.tzinfo else ns.date_to.replace(tzinfo=timezone.utc)

    runner = build_from_config(
        config=cfg, run_dir=run_dir, pairs=pairs, since=since, until=until,
    )
    runner.run(since=since, until=until)

    from crypto_farmer.backtest.report import build_report
    report = build_report(
        storage=runner._storage, since=since, until=until,
        frames=getattr(runner, "_frames", None),
        initial_cash=cfg.paper.initial_cash,
    )

    report_path = run_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    # Print robustly: Windows consoles default to cp1252 and choke on chars
    # like the arrow in the report header. The .md file keeps full UTF-8.
    try:
        print(report)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(report.encode(enc, errors="replace").decode(enc))

    if ns.export_rag:
        print(
            f"export-rag: copy {run_dir}/chroma into live RAG (manual for now)"
        )


def _run_onchain(argv) -> None:
    import argparse as _ap
    import yaml

    p = _ap.ArgumentParser(prog="crypto-farmer onchain")
    p.add_argument("--once", action="store_true",
                   help="Run a single cycle and exit.")
    p.add_argument("--config", default="config/config.yaml")
    ns = p.parse_args(argv)

    from crypto_farmer.config import load_config
    cfg = load_config(ns.config)

    with open(ns.config, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    rpc_url = os.environ.get("ONCHAIN_RPC_URL") or os.environ.get("ALCHEMY_URL")
    if not rpc_url:
        print("ERROR: set ONCHAIN_RPC_URL or ALCHEMY_URL env var", file=sys.stderr)
        sys.exit(2)

    from crypto_farmer.onchain.config import OnchainConfig
    onchain_cfg = OnchainConfig.from_dict(raw["onchain"], rpc_url=rpc_url)

    from crypto_farmer.onchain.rpc import RpcClient
    from crypto_farmer.onchain.pool_source import UniswapPoolSource
    rpc = RpcClient(url=onchain_cfg.rpc_url)
    source = UniswapPoolSource(
        rpc=rpc,
        pool_address=onchain_cfg.pool_address,
        decimals0=onchain_cfg.token0_decimals,
        decimals1=onchain_cfg.token1_decimals,
        pair_label=onchain_cfg.pair_label,
        block_time_seconds=onchain_cfg.block_time_seconds,
    )

    from crypto_farmer.llm.client import OllamaClient
    from crypto_farmer.llm.prompts import PromptBuilder
    from crypto_farmer.learning.embeddings import OllamaEmbeddings

    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    llm = OllamaClient(
        base_url=cfg.llm.base_url,
        model=cfg.llm.model,
        prompt_builder=prompt_builder,
        timeout_seconds=cfg.llm.timeout_seconds,
    )
    embeddings = OllamaEmbeddings(
        base_url=cfg.llm.base_url,
        model=cfg.llm.embedding_model,
    )

    from crypto_farmer.onchain.runner import build_onchain_cycle
    cycle = build_onchain_cycle(
        onchain_cfg=onchain_cfg,
        data_dir=Path("data/onchain"),
        market=source,
        llm_client=llm,
        embeddings=embeddings,
    )

    if ns.once:
        result = cycle.run()
        print(f"onchain cycle: {result.status.value}")
    else:
        print("Scheduled loop not wired yet — running a single cycle.")
        result = cycle.run()
        print(f"onchain cycle: {result.status.value}")


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
    if len(sys.argv) > 1 and sys.argv[1] == "onchain":
        _run_onchain(sys.argv[2:])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        _run_backtest(sys.argv[2:])
        return

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
    app.notifier.send_text("🟢 <b>Sistema iniciado</b> — crypto-farmer en marcha.")
    log.info("system_started_notified")

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
        # Best-effort: solo se envía si el proceso se cierra de forma ordenada
        # (p.ej. Ctrl+C). En un kill forzado lo manda stop.ps1 en su lugar.
        app.notifier.send_text("🔴 <b>Sistema finalizado</b> — crypto-farmer detenido.")


if __name__ == "__main__":
    main()
