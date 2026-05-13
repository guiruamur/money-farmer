from __future__ import annotations

from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse


class FakeLLMClient:
    def __init__(self, *, responses: list[RawLLMResponse]) -> None:
        assert responses
        self._responses = responses
        self._idx = 0

    def analyze(self, context: AnalysisContext) -> RawLLMResponse:
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp
