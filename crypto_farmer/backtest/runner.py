from __future__ import annotations

from datetime import datetime, timedelta
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
                 metrics, pairs, chroma_dir, timeframe="15m") -> "BacktestRunner":
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
        prefilter = Prefilter(PrefilterConfig(
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
            pairs=pairs, timeframe=timeframe, ohlcv_lookback=200,
            min_confidence=60, news_max_age_hours=24,
            memory_k=3, feedback_lookback=20,
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
