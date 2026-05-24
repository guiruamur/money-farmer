from __future__ import annotations

from pathlib import Path

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.backtest.null_notifier import NullNotifier
from crypto_farmer.clock import SystemClock
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.data.news import NoopNewsSource
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import ChromaMemory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.metrics import Metrics
from crypto_farmer.onchain.config import OnchainConfig
from crypto_farmer.storage.db import Storage


def build_onchain_cycle(*, onchain_cfg: OnchainConfig, data_dir: Path,
                        market, llm_client, embeddings) -> Cycle:
    data_dir.mkdir(parents=True, exist_ok=True)
    clock = SystemClock()
    storage = Storage(db_path=str(data_dir / "crypto_farmer.db"), clock=clock)
    memory = ChromaMemory(persist_dir=str(data_dir / "chroma"), collection_name="onchain")
    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    parser = SignalParser(llm_client=llm_client, max_retries=0)
    feedback = FeedbackBuilder(storage=storage)
    outcomes = OutcomeService(storage=storage, market=market,
                              horizons_hours=[1, 4, 24], memory=memory)
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
        notifier=NullNotifier(), storage=storage, metrics=Metrics(),
        pairs=[onchain_cfg.pair_label], timeframe="15m", ohlcv_lookback=200,
        min_confidence=60, news_max_age_hours=24,
        memory_k=3, feedback_lookback=20,
        paper_trader=None, clock=clock,
    )
    return Cycle(deps)
