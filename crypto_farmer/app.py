from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import httpx
from telegram import Bot

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.config import Config, load_config
from crypto_farmer.clock import SystemClock
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.data.market import CcxtBinanceSource
from crypto_farmer.data.news import CryptoPanicSource, NoopNewsSource
from crypto_farmer.delivery.bot_commands import BotCommands, CommandContext
from crypto_farmer.delivery.digest import DigestSender
from crypto_farmer.delivery.telegram import TelegramNotifier
from crypto_farmer.learning.embeddings import OllamaEmbeddings
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import ChromaMemory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.llm.client import OllamaClient
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.logging_setup import configure_logging, get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.paper.trader import PaperTrader, PaperTraderConfig
from crypto_farmer.scheduler import CycleScheduler
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


@dataclass
class App:
    config: Config
    cycle: Cycle
    scheduler: CycleScheduler
    bot_commands: BotCommands
    storage: Storage
    metrics: Metrics
    notifier: TelegramNotifier


def _health_checker(*, ollama_base: str, db_path: str, chroma_path: str):
    def check() -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            with httpx.Client(timeout=3.0) as c:
                r = c.get(f"{ollama_base}/api/tags")
                out["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            out["ollama"] = f"down ({e})"
        out["sqlite"] = "ok" if Path(db_path).exists() else "missing"
        out["chromadb"] = "ok" if Path(chroma_path).exists() else "not_initialized"
        try:
            ex = ccxt.binance({"enableRateLimit": True})
            ex.fetch_status()
            out["binance"] = "ok"
        except Exception as e:
            out["binance"] = f"down ({e})"
        return out
    return check


def build_app(*, config_path: str | Path) -> App:
    cfg = load_config(config_path)
    configure_logging(
        level=cfg.logging.level,
        json_format=cfg.logging.format == "json",
        to_stdout=True,
        log_file=cfg.logging.file,
        retention_days=cfg.logging.retention_days,
    )

    metrics = Metrics()
    clock = SystemClock()
    storage = Storage(db_path=cfg.storage.sqlite_path, clock=clock)

    market = CcxtBinanceSource(exchange=ccxt.binance({"enableRateLimit": True}))
    news = (
        CryptoPanicSource(token=cfg.news_credentials.cryptopanic_token)
        if cfg.news.enabled
        else NoopNewsSource()
    )

    indicators = IndicatorEngine()
    prefilter = Prefilter(PrefilterConfig(
        rsi_oversold=cfg.prefilter.rsi_oversold,
        rsi_overbought=cfg.prefilter.rsi_overbought,
        volume_anomaly_factor=cfg.prefilter.volume_anomaly_factor,
        atr_expansion_factor=cfg.prefilter.atr_expansion_factor,
        cooldown_minutes=cfg.prefilter.cooldown_minutes,
    ))

    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    llm = OllamaClient(
        base_url=cfg.llm.base_url, model=cfg.llm.model,
        prompt_builder=prompt_builder, timeout_seconds=cfg.llm.timeout_seconds,
        clock=clock,
    )
    parser = SignalParser(llm_client=llm, max_retries=cfg.llm.max_retries)

    embeddings = OllamaEmbeddings(
        base_url=cfg.llm.base_url, model=cfg.llm.embedding_model,
    )
    memory = ChromaMemory(persist_dir=cfg.storage.chroma_path, collection_name="situations")
    feedback = FeedbackBuilder(storage=storage)
    outcomes = OutcomeService(
        storage=storage, market=market,
        horizons_hours=cfg.learning.outcome_horizons_hours, memory=memory,
    )

    bot = Bot(token=cfg.delivery.telegram.bot_token)
    notifier = TelegramNotifier(bot=bot, chat_id=cfg.delivery.telegram.chat_id)

    paper_trader: PaperTrader | None = None
    if cfg.paper.enabled:
        paper_trader = PaperTrader(
            storage=storage,
            config=PaperTraderConfig(
                initial_cash=cfg.paper.initial_cash,
                position_size_pct=cfg.paper.position_size_pct,
                vault_pct=cfg.paper.vault_pct,
                fee_rate=cfg.paper.fee_rate,
            ),
        )

    deps = CycleDeps(
        market=market, news=news,
        indicators=indicators, prefilter=prefilter,
        prompt_builder=prompt_builder, parser=parser,
        embeddings=embeddings, memory=memory,
        feedback=feedback, outcomes=outcomes,
        notifier=notifier, storage=storage, metrics=metrics,
        pairs=cfg.market.pairs, timeframe=cfg.market.timeframe,
        ohlcv_lookback=cfg.market.ohlcv_lookback,
        min_confidence=cfg.delivery.telegram.min_confidence,
        news_max_age_hours=cfg.news.max_age_hours,
        memory_k=cfg.learning.memory_k,
        feedback_lookback=cfg.learning.feedback_lookback,
        paper_trader=paper_trader,
        clock=clock,
    )
    cycle = Cycle(deps)

    digest = DigestSender(
        storage=storage,
        bot=bot,
        chat_id=cfg.delivery.telegram.chat_id,
        lookback_hours=cfg.delivery.telegram.digest_lookback_hours,
        memory_count_fn=lambda: memory._collection.count(),  # ChromaMemory internal
    )

    scheduler = CycleScheduler(
        interval_minutes=cfg.scheduler.interval_minutes,
        timezone=cfg.scheduler.timezone,
        cycle_callable=cycle.run,
        outcomes_callable=lambda: outcomes.run_due_jobs(now=datetime.now(timezone.utc)),
        digest_callable=digest.send,
        digest_minutes=cfg.delivery.telegram.digest_minutes,
    )

    bot_ctx = CommandContext(
        storage=storage,
        scheduler_paused_getter=scheduler.is_paused,
        scheduler_pauser=scheduler.pause,
        scheduler_resumer=scheduler.resume,
        health_checker=_health_checker(
            ollama_base=cfg.llm.base_url,
            db_path=cfg.storage.sqlite_path,
            chroma_path=cfg.storage.chroma_path,
        ),
        config_snapshot=cfg.model_dump(),
    )
    bot_commands = BotCommands(bot_ctx)

    return App(
        config=cfg, cycle=cycle, scheduler=scheduler,
        bot_commands=bot_commands, storage=storage, metrics=metrics,
        notifier=notifier,
    )
