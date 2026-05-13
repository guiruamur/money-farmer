from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.signals.models import IndicatorSnapshot
from tests.fakes.llm import FakeLLMClient
from datetime import datetime, timezone


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28.0, macd=1.0, macd_signal=0.0, macd_hist=1.0,
        ema_20=100.0, ema_50=99.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0,
        volume=120.0, volume_mean_24h=100.0,
    )
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=snap, ohlcv_summary={}, news=[],
        memory_hits=[], recent_feedback={"win_rate": 0, "summary": "n/a"},
    )


def test_fake_returns_configured_response():
    fake = FakeLLMClient(responses=[RawLLMResponse(text='{"action":"BUY"}')])
    resp = fake.analyze(_ctx())
    assert resp.text == '{"action":"BUY"}'


def test_fake_cycles_through_responses():
    fake = FakeLLMClient(responses=[
        RawLLMResponse(text="a"), RawLLMResponse(text="b"),
    ])
    assert fake.analyze(_ctx()).text == "a"
    assert fake.analyze(_ctx()).text == "b"
    assert fake.analyze(_ctx()).text == "a"  # vuelve a empezar
