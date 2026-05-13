from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from crypto_farmer.signals.models import IndicatorSnapshot


@dataclass
class AnalysisContext:
    pair: str
    timeframe: str
    indicators: IndicatorSnapshot
    ohlcv_summary: dict[str, Any]
    news: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]
    recent_feedback: dict[str, Any]
    portfolio_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawLLMResponse:
    text: str
    latency_ms: int = 0


class LLMClient(Protocol):
    def analyze(self, context: AnalysisContext) -> RawLLMResponse: ...
