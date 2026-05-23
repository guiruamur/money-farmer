from datetime import datetime, timezone

from crypto_farmer.backtest.llm_cache import CachedLLMClient
from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.signals.models import IndicatorSnapshot


class _CountingClient:
    def __init__(self): self.calls = 0
    def analyze(self, context):
        self.calls += 1
        return RawLLMResponse(text='{"hit": %d}' % self.calls)


def _ctx(pair="BTC/USDT"):
    return AnalysisContext(
        pair=pair, timeframe="15m",
        indicators=IndicatorSnapshot(
            pair=pair,
            timestamp=datetime(2026, 5, 17, tzinfo=timezone.utc),
            rsi=0.0,
            macd=0.0,
            macd_signal=0.0,
            macd_hist=0.0,
            ema_20=0.0,
            ema_50=0.0,
            bb_upper=0.0,
            bb_lower=0.0,
            atr=0.0,
            atr_mean_20=0.0,
            volume=0.0,
            volume_mean_24h=0.0,
        ),
        ohlcv_summary={"close": 100}, news=[], memory_hits=[], recent_feedback={},
    )


def test_cache_miss_then_hit(tmp_path):
    inner = _CountingClient()
    c = CachedLLMClient(inner=inner, db_path=tmp_path / "cache.sqlite")
    r1 = c.analyze(_ctx())
    r2 = c.analyze(_ctx())  # identical context -> served from cache
    assert inner.calls == 1
    assert r1.text == r2.text


def test_cache_distinguishes_contexts(tmp_path):
    inner = _CountingClient()
    c = CachedLLMClient(inner=inner, db_path=tmp_path / "cache.sqlite")
    c.analyze(_ctx("BTC/USDT"))
    c.analyze(_ctx("ETH/USDT"))
    assert inner.calls == 2


def test_cache_persists_across_instances(tmp_path):
    db = tmp_path / "cache.sqlite"
    inner1 = _CountingClient()
    CachedLLMClient(inner=inner1, db_path=db).analyze(_ctx())
    inner2 = _CountingClient()
    CachedLLMClient(inner=inner2, db_path=db).analyze(_ctx())
    assert inner1.calls == 1
    assert inner2.calls == 0  # second instance reads from disk
