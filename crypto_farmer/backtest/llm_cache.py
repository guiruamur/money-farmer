from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from crypto_farmer.llm.client import AnalysisContext, LLMClient, RawLLMResponse


def _key(ctx: AnalysisContext) -> str:
    payload = {
        "pair": ctx.pair,
        "timeframe": ctx.timeframe,
        "indicators": ctx.indicators.model_dump(mode="json"),
        "ohlcv_summary": ctx.ohlcv_summary,
        "news": ctx.news,
        "memory_hits": ctx.memory_hits,
        "recent_feedback": ctx.recent_feedback,
        "portfolio_state": ctx.portfolio_state,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class CachedLLMClient:
    """Wraps an LLMClient; caches responses keyed by the analysis context.

    The key is the situation (indicators, summary, memory, portfolio) — NOT the
    timestamp — so 'same situation -> same decision', which gives reproducible,
    reusable runs.
    """

    def __init__(self, *, inner: LLMClient, db_path: str | Path) -> None:
        self._inner = inner
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS llm_cache (k TEXT PRIMARY KEY, text TEXT)")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def analyze(self, context: AnalysisContext) -> RawLLMResponse:
        k = _key(context)
        with self._conn() as c:
            row = c.execute("SELECT text FROM llm_cache WHERE k=?", (k,)).fetchone()
            if row is not None:
                return RawLLMResponse(text=row[0])
        resp = self._inner.analyze(context)
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO llm_cache (k, text) VALUES (?, ?)", (k, resp.text))
            c.commit()
        return resp
