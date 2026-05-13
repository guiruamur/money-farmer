from datetime import datetime, timezone

import httpx
import pytest
import respx

from crypto_farmer.llm.client import (
    AnalysisContext, LLMCallError, OllamaClient,
)
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28, macd=1, macd_signal=0, macd_hist=1,
        ema_20=100, ema_50=99, bb_upper=110, bb_lower=90,
        atr=5, atr_mean_20=4, volume=120, volume_mean_24h=100,
    )
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m", indicators=snap,
        ohlcv_summary=OHLCVSummary(
            recent=[OHLCVCandle(open=1, high=2, low=0.5, close=1.5, volume=1)],
            highest_high=2, lowest_low=0.5,
        ).model_dump(),
        news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


@respx.mock
def test_ollama_client_returns_text(tmp_path):
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": '{"action":"HOLD"}'}})
    )
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    client = OllamaClient(
        base_url="http://localhost:11434", model="qwen2.5",
        prompt_builder=builder, timeout_seconds=10, http_client=httpx.Client(),
    )
    resp = client.analyze(_ctx())
    assert resp.text == '{"action":"HOLD"}'


@respx.mock
def test_ollama_client_raises_on_http_error():
    respx.post("http://localhost:11434/api/chat").mock(return_value=httpx.Response(500))
    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    client = OllamaClient(
        base_url="http://localhost:11434", model="qwen2.5",
        prompt_builder=builder, timeout_seconds=10, http_client=httpx.Client(),
    )
    with pytest.raises(LLMCallError):
        client.analyze(_ctx())
