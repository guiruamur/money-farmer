import os

import httpx
import pytest

from crypto_farmer.llm.client import AnalysisContext, OllamaClient
from crypto_farmer.llm.parser import SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary


pytestmark = pytest.mark.llm


def _skip_if_disabled():
    if os.environ.get("RUN_LLM_TESTS") != "1":
        pytest.skip("RUN_LLM_TESTS!=1")
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2.0)
    except Exception:
        pytest.skip("ollama not reachable")


def test_real_ollama_produces_valid_json():
    _skip_if_disabled()
    from datetime import datetime, timezone

    builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    llm = OllamaClient(
        base_url="http://localhost:11434",
        model=os.environ.get("LLM_TEST_MODEL", "qwen2.5:7b-instruct-q4_K_M"),
        prompt_builder=builder, timeout_seconds=60,
    )
    parser = SignalParser(llm_client=llm, max_retries=1)
    ctx = AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=IndicatorSnapshot(
            pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
            rsi=28, macd=0.5, macd_signal=0.3, macd_hist=0.2,
            ema_20=100, ema_50=99, bb_upper=110, bb_lower=90,
            atr=5, atr_mean_20=4, volume=120, volume_mean_24h=100,
        ),
        ohlcv_summary=OHLCVSummary(
            recent=[OHLCVCandle(open=100, high=101, low=99, close=100.5, volume=1)],
            highest_high=101, lowest_low=99,
        ).model_dump(),
        news=[], memory_hits=[],
        recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )
    out = parser.analyze_with_retry(ctx)
    assert out.signal.action.value in {"BUY", "SELL", "HOLD"}
    assert 0 <= out.signal.confidence <= 100
