from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

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


class LLMCallError(Exception):
    pass


class OllamaClient:
    def __init__(
        self, *, base_url: str, model: str,
        prompt_builder: Any,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._prompt_builder = prompt_builder
        self._timeout = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def analyze(self, context: AnalysisContext) -> RawLLMResponse:
        prompt = self._prompt_builder.render(context, now=datetime.now(timezone.utc))
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._prompt_builder.system_message()},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.2},
        }
        t0 = time.monotonic()
        try:
            r = self._client.post(f"{self._base}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMCallError(f"ollama: {e}") from e
        latency_ms = int((time.monotonic() - t0) * 1000)
        text = r.json().get("message", {}).get("content", "")
        return RawLLMResponse(text=text, latency_ms=latency_ms)
