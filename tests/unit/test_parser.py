import pytest

from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.llm.parser import (
    LLMParseError, SignalParser, parse_signal_strict,
)
from crypto_farmer.signals.models import SignalAction


def test_parse_strict_ok():
    raw = '{"action":"BUY","confidence":75,"reasoning":"r","entry_price_hint":100.0,"invalidation_level":95.0,"time_horizon":"short","key_factors":["x"]}'
    s = parse_signal_strict(raw)
    assert s.action == SignalAction.BUY
    assert s.confidence == 75


def test_parse_strict_rejects_invalid_json():
    with pytest.raises(LLMParseError):
        parse_signal_strict("not-json")


def test_parse_strict_rejects_bad_schema():
    with pytest.raises(LLMParseError):
        parse_signal_strict('{"action":"INVALID","confidence":5,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}')


class _StubClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def analyze(self, ctx):
        self.calls += 1
        return RawLLMResponse(text=self._responses.pop(0))


def _ctx_stub() -> AnalysisContext:
    from datetime import datetime, timezone
    from crypto_farmer.signals.models import IndicatorSnapshot
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=IndicatorSnapshot(
            pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
            rsi=28, macd=0, macd_signal=0, macd_hist=0,
            ema_20=100, ema_50=100, bb_upper=110, bb_lower=90,
            atr=5, atr_mean_20=5, volume=100, volume_mean_24h=100,
        ),
        ohlcv_summary={}, news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


def test_parser_with_retry_succeeds_second_time():
    stub = _StubClient(responses=[
        "garbage",
        '{"action":"BUY","confidence":70,"reasoning":"r","entry_price_hint":null,"invalidation_level":null,"time_horizon":"short","key_factors":[]}',
    ])
    parser = SignalParser(llm_client=stub, max_retries=1)
    out = parser.analyze_with_retry(_ctx_stub())
    assert out.signal.action == SignalAction.BUY
    assert stub.calls == 2
    assert out.raw_text.startswith('{"action":"BUY"')


def test_parser_with_retry_gives_up():
    stub = _StubClient(responses=["g1", "g2"])
    parser = SignalParser(llm_client=stub, max_retries=1)
    with pytest.raises(LLMParseError):
        parser.analyze_with_retry(_ctx_stub())
    assert stub.calls == 2
