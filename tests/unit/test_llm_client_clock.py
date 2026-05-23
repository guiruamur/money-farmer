from datetime import datetime, timezone

import httpx
import respx

from crypto_farmer.llm.client import OllamaClient, AnalysisContext
from crypto_farmer.signals.models import IndicatorSnapshot


class _FrozenClock:
    def __init__(self, t): self._t = t
    def now(self): return self._t


class _RecordingPromptBuilder:
    def __init__(self): self.seen_now = None
    def system_message(self): return "sys"
    def render(self, context, now): self.seen_now = now; return "PROMPT"


def _ctx():
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m",
        indicators=IndicatorSnapshot(
            pair="BTC/USDT",
            timestamp=datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc),
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
        ohlcv_summary={}, news=[], memory_hits=[], recent_feedback={},
    )


@respx.mock
def test_ollama_client_renders_with_injected_clock():
    respx.post("http://x/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "{}"}})
    )
    frozen = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    pb = _RecordingPromptBuilder()
    client = OllamaClient(
        base_url="http://x", model="m", prompt_builder=pb,
        timeout_seconds=5, clock=_FrozenClock(frozen),
    )
    client.analyze(_ctx())
    assert pb.seen_now == frozen
