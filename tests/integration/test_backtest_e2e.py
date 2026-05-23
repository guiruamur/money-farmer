from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import HistoricalMarketSource
from crypto_farmer.backtest.runner import BacktestRunner, candle_times
from crypto_farmer.clock import BacktestClock
from crypto_farmer.backtest.null_notifier import NullNotifier
from crypto_farmer.llm.client import RawLLMResponse
from crypto_farmer.metrics import Metrics
from crypto_farmer.storage.db import Storage


def test_candle_times_15m():
    start = datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
    ts = candle_times(start, end, "15m")
    assert ts[0] == start
    assert ts[-1] == end
    assert len(ts) == 5


def _trending_df(n=120):
    base = datetime(2026, 5, 17, tzinfo=timezone.utc)
    rows = [
        {"timestamp": pd.Timestamp(base) + pd.Timedelta(minutes=15 * i),
         "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 100 + (i % 5)}
        for i in range(n)
    ]
    return pd.DataFrame(rows)


class _AlwaysHoldLLM:
    def analyze(self, context):
        return RawLLMResponse(text='{"action":"HOLD","confidence":50,'
                                   '"reasoning":"r","time_horizon":"short","key_factors":[],'
                                   '"entry_price_hint":null,"invalidation_level":null}')


class _FakeEmbeddings:
    def embed(self, text): return [0.0, 0.0, 0.0]


def test_backtest_runs_and_isolates_data(tmp_path):
    clock = BacktestClock()
    frames = {"BTC/USDT": _trending_df()}
    run_dir = tmp_path / "run"
    storage = Storage(db_path=run_dir / "bt.db", clock=clock)
    market = HistoricalMarketSource(clock=clock, frames=frames)

    runner = BacktestRunner.for_test(
        clock=clock, storage=storage, market=market,
        llm_client=_AlwaysHoldLLM(), embeddings=_FakeEmbeddings(),
        notifier=NullNotifier(), metrics=Metrics(),
        pairs=["BTC/USDT"], chroma_dir=run_dir / "chroma",
    )

    start = datetime(2026, 5, 17, 6, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 7, 0, tzinfo=timezone.utc)
    runner.run(since=start, until=end)

    cycles = storage.list_recent_cycles(limit=100)
    assert len(cycles) == 5
    assert all(c["status"] in ("ok", "degraded") for c in cycles)
