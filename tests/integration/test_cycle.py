from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.learning.embeddings import Embeddings
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.llm.client import RawLLMResponse
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.metrics import Metrics
from crypto_farmer.signals.models import CycleStatus
from crypto_farmer.storage.db import Storage
from tests.fakes.llm import FakeLLMClient
from tests.fakes.market import FakeMarketDataSource
from tests.fakes.memory import InMemoryMemory
from tests.fakes.news import FakeNewsSource
from tests.fakes.notifier import FakeNotifier


class _FakeEmbeddings:
    def embed(self, text: str) -> list[float]:
        return [float(len(text)), float(sum(ord(c) for c in text[:5]))]


def _ohlcv(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed=seed)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": base,
        "high": base + np.abs(rng.normal(0, 1, n)) + 1,
        "low": base - np.abs(rng.normal(0, 1, n)) - 1,
        "close": base + rng.normal(0, 0.3, n),
        "volume": rng.uniform(50, 150, n),
    })


def _build_cycle(tmp_path: Path, llm_responses=None, news=None):
    storage = Storage(db_path=tmp_path / "cycle.db")
    market = FakeMarketDataSource(ohlcv={
        "BTC/USDT": _ohlcv(seed=1),
        "ETH/USDT": _ohlcv(seed=2),
    }, tickers={
        "BTC/USDT": (100.0, datetime.now(timezone.utc)),
        "ETH/USDT": (2000.0, datetime.now(timezone.utc)),
    })
    news_src = FakeNewsSource(items=news or [])
    indicators = IndicatorEngine()
    prefilter = Prefilter(PrefilterConfig(
        rsi_oversold=80, rsi_overbought=20,  # umbrales que hacen todo pasar
        volume_anomaly_factor=10, atr_expansion_factor=10, cooldown_minutes=0,
    ))
    llm_resp = llm_responses or [RawLLMResponse(text='{"action":"BUY","confidence":70,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')]
    llm_client = FakeLLMClient(responses=llm_resp)
    parser = SignalParser(llm_client=llm_client, max_retries=0)
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    memory = InMemoryMemory()
    embeddings: Embeddings = _FakeEmbeddings()
    feedback = FeedbackBuilder(storage=storage)
    outcomes = OutcomeService(
        storage=storage, market=market,
        horizons_hours=[1, 4, 24], memory=memory,
    )
    notifier = FakeNotifier()
    metrics = Metrics()

    deps = CycleDeps(
        market=market, news=news_src,
        indicators=indicators, prefilter=prefilter,
        prompt_builder=builder, parser=parser,
        embeddings=embeddings, memory=memory,
        feedback=feedback, outcomes=outcomes,
        notifier=notifier, storage=storage,
        metrics=metrics,
        pairs=["BTC/USDT", "ETH/USDT"], timeframe="15m", ohlcv_lookback=120,
        min_confidence=60, news_max_age_hours=4, memory_k=5,
        feedback_lookback=20,
    )
    return Cycle(deps), storage, notifier, metrics


def test_cycle_runs_end_to_end(tmp_path: Path):
    cycle, storage, notifier, metrics = _build_cycle(tmp_path)
    result = cycle.run()
    assert result.status == CycleStatus.OK
    assert result.pairs_analyzed == 2
    assert result.pairs_passed_prefilter > 0
    assert result.signals_generated >= 1
    assert len(notifier.delivered) >= 1
    snap = metrics.snapshot()
    assert snap["counters"].get("signals_generated", 0) >= 1


def test_cycle_persists_signals_and_contexts(tmp_path: Path):
    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle.run()
    signals = storage.list_recent_signals(limit=10)
    assert signals
    ctx = storage.get_analysis_context(signals[0]["id"])
    assert ctx is not None
    assert ctx["prompt_rendered"]
    # Every generated signal must have a memory_entry_id persisted
    for sig in signals:
        row = storage.get_signal_by_id(signal_id=sig["id"])
        assert row is not None
        assert row.get("memory_entry_id") is not None, (
            f"signal {sig['id']} missing memory_entry_id"
        )


def test_cycle_degraded_when_news_fails(tmp_path: Path):
    class _BrokenNews:
        def fetch_recent(self, since):
            from crypto_farmer.data.news import NewsFetchError
            raise NewsFetchError("simulated")

    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle._deps.news = _BrokenNews()
    result = cycle.run()
    assert result.status == CycleStatus.DEGRADED
    assert "news" in (result.notes or "").lower()


def test_cycle_skips_low_confidence_signal_delivery(tmp_path: Path):
    low_conf = RawLLMResponse(text='{"action":"BUY","confidence":40,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')
    cycle, storage, notifier, _ = _build_cycle(tmp_path, llm_responses=[low_conf])
    cycle.run()
    signals = storage.list_recent_signals(limit=10)
    assert signals
    assert all(s["delivered"] == 0 for s in signals)
    assert notifier.delivered == []


def test_cycle_schedules_outcome_jobs(tmp_path: Path):
    cycle, storage, notifier, _ = _build_cycle(tmp_path)
    cycle.run()
    now = datetime.now(timezone.utc)
    due = storage.list_due_outcome_jobs(now=now + timedelta(hours=25))
    assert len(due) >= 3
