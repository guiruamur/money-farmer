from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from crypto_farmer.llm.client import AnalysisContext, LLMClient
from crypto_farmer.signals.models import Signal


class LLMParseError(Exception):
    pass


@dataclass
class ParsedSignal:
    signal: Signal
    raw_text: str
    attempts: int


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    # Acepta JSON pelado o JSON dentro de bloque "```json ... ```"
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    match = _JSON_BLOCK.search(text)
    if match:
        return match.group(0)
    return text


def parse_signal_strict(text: str) -> Signal:
    json_text = _extract_json(text)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise LLMParseError(f"json inválido: {e}") from e
    try:
        return Signal.model_validate(data)
    except ValidationError as e:
        raise LLMParseError(f"schema inválido: {e}") from e


class SignalParser:
    RETRY_PREFIX = (
        "Tu respuesta anterior no fue JSON válido. Responde EXCLUSIVAMENTE con "
        "el JSON pedido, sin texto adicional:"
    )

    def __init__(self, *, llm_client: LLMClient, max_retries: int) -> None:
        self._client = llm_client
        self._max_retries = max_retries

    def analyze_with_retry(self, context: AnalysisContext) -> ParsedSignal:
        attempts = 0
        last_error: Exception | None = None
        last_text = ""
        while attempts <= self._max_retries:
            attempts += 1
            resp = self._client.analyze(context)
            last_text = resp.text
            try:
                signal = parse_signal_strict(resp.text)
                return ParsedSignal(signal=signal, raw_text=resp.text, attempts=attempts)
            except LLMParseError as e:
                last_error = e
        raise LLMParseError(
            f"parse falló tras {attempts} intentos: {last_error}; texto final: {last_text[:200]}"
        )
