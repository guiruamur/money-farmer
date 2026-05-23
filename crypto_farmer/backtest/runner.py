from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.backtest.market import HistoricalMarketSource, OhlcvStore
from crypto_farmer.clock import BacktestClock
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.data.news import NoopNewsSource
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import ChromaMemory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.storage.db import Storage

log = get_logger(__name__)

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def candle_times(since: datetime, until: datetime, timeframe: str) -> list[datetime]:
    step = timedelta(minutes=_TF_MINUTES[timeframe])
    out, t = [], since
    while t <= until:
        out.append(t)
        t += step
    return out


class BacktestRunner:
    def __init__(self, *, clock: BacktestClock, cycle: Cycle, outcomes: OutcomeService,
                 timeframe: str) -> None:
        self._clock = clock
        self._cycle = cycle
        self._outcomes = outcomes
        self._tf = timeframe
        self._storage = None

    @classmethod
    def for_test(cls, *, clock, storage, market, llm_client, embeddings, notifier,
                 metrics, pairs, chroma_dir, timeframe="15m",
                 prefilter_config: PrefilterConfig | None = None,
                 min_confidence: int = 60, ohlcv_lookback: int = 200,
                 news_max_age_hours: int = 24, memory_k: int = 3,
                 feedback_lookback: int = 20) -> "BacktestRunner":
        from crypto_farmer.llm.parser import SignalParser
        from crypto_farmer.llm.prompts import PromptBuilder

        memory = ChromaMemory(persist_dir=str(chroma_dir), collection_name="backtest")
        prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
        parser = SignalParser(llm_client=llm_client, max_retries=0)
        feedback = FeedbackBuilder(storage=storage)
        outcomes = OutcomeService(
            storage=storage, market=market,
            horizons_hours=[1, 4, 24], memory=memory,
        )
        prefilter = Prefilter(prefilter_config or PrefilterConfig(
            rsi_oversold=30, rsi_overbought=70, volume_anomaly_factor=1.8,
            atr_expansion_factor=1.5, cooldown_minutes=0,
        ))
        deps = CycleDeps(
            market=market, news=NoopNewsSource(),
            indicators=IndicatorEngine(), prefilter=prefilter,
            prompt_builder=prompt_builder, parser=parser,
            embeddings=embeddings, memory=memory,
            feedback=feedback, outcomes=outcomes,
            notifier=notifier, storage=storage, metrics=metrics,
            pairs=pairs, timeframe=timeframe, ohlcv_lookback=ohlcv_lookback,
            min_confidence=min_confidence, news_max_age_hours=news_max_age_hours,
            memory_k=memory_k, feedback_lookback=feedback_lookback,
            paper_trader=None, clock=clock,
        )
        runner = cls(clock=clock, cycle=Cycle(deps), outcomes=outcomes, timeframe=timeframe)
        runner._storage = storage
        return runner

    def run(self, *, since: datetime, until: datetime) -> None:
        for t in candle_times(since, until, self._tf):
            self._clock.current = t
            self._cycle.run()
            self._outcomes.run_due_jobs(now=t)
        drain_end = until + timedelta(hours=24)
        for t in candle_times(until, drain_end, self._tf):
            self._clock.current = t
            self._outcomes.run_due_jobs(now=t)
        log.info("backtest_finished", extra={"since": since.isoformat(), "until": until.isoformat()})


def build_from_config(*, config, run_dir: Path, pairs: list[str],
                      since: datetime, until: datetime) -> "BacktestRunner":
    import ccxt
    from crypto_farmer.backtest.llm_cache import CachedLLMClient
    from crypto_farmer.backtest.null_notifier import NullNotifier
    from crypto_farmer.llm.client import OllamaClient
    from crypto_farmer.llm.prompts import PromptBuilder
    from crypto_farmer.learning.embeddings import OllamaEmbeddings
    from crypto_farmer.paper.trader import PaperTrader, PaperTraderConfig

    run_dir.mkdir(parents=True, exist_ok=True)
    clock = BacktestClock()
    storage = Storage(db_path=str(run_dir / "crypto_farmer.db"), clock=clock)

    tf = config.market.timeframe
    lookback = config.market.ohlcv_lookback
    margin = timedelta(minutes=_TF_MINUTES[tf] * lookback)
    store = OhlcvStore(exchange=ccxt.binance({"enableRateLimit": True}))
    frames = {
        p: store.load(pair=p, timeframe=tf, since=since - margin, until=until + timedelta(hours=24))
        for p in pairs
    }
    market = HistoricalMarketSource(clock=clock, frames=frames)

    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    inner = OllamaClient(
        base_url=config.llm.base_url, model=config.llm.model,
        prompt_builder=prompt_builder, timeout_seconds=config.llm.timeout_seconds,
        clock=clock,
    )
    cached = CachedLLMClient(inner=inner, db_path="data/backtest/llm_cache.sqlite")
    embeddings = OllamaEmbeddings(base_url=config.llm.base_url, model=config.llm.embedding_model)

    # Build the prefilter and decision params FROM THE CONFIG so the backtest
    # faithfully reflects the live strategy (and can be tuned via --config).
    prefilter_config = PrefilterConfig(
        rsi_oversold=config.prefilter.rsi_oversold,
        rsi_overbought=config.prefilter.rsi_overbought,
        volume_anomaly_factor=config.prefilter.volume_anomaly_factor,
        atr_expansion_factor=config.prefilter.atr_expansion_factor,
        cooldown_minutes=config.prefilter.cooldown_minutes,
    )
    runner = BacktestRunner.for_test(
        clock=clock, storage=storage, market=market,
        llm_client=cached, embeddings=embeddings, notifier=NullNotifier(),
        metrics=Metrics(), pairs=pairs, chroma_dir=run_dir / "chroma", timeframe=tf,
        prefilter_config=prefilter_config,
        min_confidence=config.delivery.telegram.min_confidence,
        ohlcv_lookback=config.market.ohlcv_lookback,
        news_max_age_hours=config.news.max_age_hours,
        memory_k=config.learning.memory_k,
        feedback_lookback=config.learning.feedback_lookback,
    )

    if config.paper.enabled:
        paper = PaperTrader(storage=storage, config=PaperTraderConfig(
            initial_cash=config.paper.initial_cash,
            position_size_pct=config.paper.position_size_pct,
            vault_pct=config.paper.vault_pct, fee_rate=config.paper.fee_rate,
        ))
        runner._cycle._deps.paper_trader = paper  # explicit backtest wiring

    runner._frames = frames
    return runner
