# Backtesting Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replay the live `Cycle` over a historical date range to evaluate the strategy in minutes instead of weeks, producing a performance report and an isolated RAG memory.

**Architecture:** Introduce an injectable `Clock` so the decision path's notion of "now" can be moved into the past. A `HistoricalMarketSource` serves candles up to the clock's instant; a `BacktestRunner` steps the clock candle-by-candle reusing the real `Cycle.run()`. An LLM response cache makes re-runs fast. All backtest data lives under `data/backtest/<run_id>/`, never touching the live system.

**Tech Stack:** Python 3.11+, pandas, ccxt, pydantic, pytest, sqlite3, chromadb.

**Branch:** Implement on a dedicated branch (e.g. `feat/backtesting`), never on `master` while the live bot runs. The clock refactor touches production files; tests guard it.

---

## File structure

**New files:**
- `crypto_farmer/clock.py` — `Clock` protocol, `SystemClock`, `BacktestClock`.
- `crypto_farmer/backtest/__init__.py` — empty package marker.
- `crypto_farmer/backtest/market.py` — `OhlcvStore`, `HistoricalMarketSource`.
- `crypto_farmer/backtest/llm_cache.py` — `CachedLLMClient`.
- `crypto_farmer/backtest/null_notifier.py` — `NullNotifier` (no-op Notifier for backtests).
- `crypto_farmer/backtest/runner.py` — `build_backtest_deps`, `BacktestRunner`.
- `crypto_farmer/backtest/report.py` — `BacktestReport`.
- Tests under `tests/unit/` (one per module) and `tests/integration/test_backtest_e2e.py`.

**Modified files (the clock refactor — the only production changes):**
- `crypto_farmer/storage/db.py` — inject `clock`, stamp with `clock.now()`.
- `crypto_farmer/llm/client.py` — inject `clock`, render prompt with `clock.now()`.
- `crypto_farmer/cycle.py` — add `clock` to `CycleDeps`, replace 4 `datetime.now()` calls, pass `now` to paper trader.
- `crypto_farmer/app.py` — build `SystemClock()` and wire it in.
- `crypto_farmer/__main__.py` — add the `backtest` subcommand.

---

## Task 1: The Clock

**Files:**
- Create: `crypto_farmer/clock.py`
- Test: `tests/unit/test_clock.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_clock.py
from datetime import datetime, timezone

from crypto_farmer.clock import BacktestClock, SystemClock


def test_system_clock_returns_aware_utc_now():
    before = datetime.now(timezone.utc)
    got = SystemClock().now()
    after = datetime.now(timezone.utc)
    assert got.tzinfo is timezone.utc
    assert before <= got <= after


def test_backtest_clock_returns_current():
    c = BacktestClock()
    t = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
    c.current = t
    assert c.now() == t


def test_backtest_clock_advances():
    c = BacktestClock()
    c.current = datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc)
    first = c.now()
    c.current = datetime(2026, 5, 17, 0, 15, tzinfo=timezone.utc)
    assert c.now() > first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_clock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crypto_farmer.clock'`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/clock.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real wall-clock time (production)."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class BacktestClock:
    """Clock the backtest runner moves through historical instants."""

    def __init__(self) -> None:
        self.current: datetime = datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self.current
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_clock.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/clock.py tests/unit/test_clock.py
git commit -m "feat(clock): injectable Clock with System and Backtest impls"
```

---

## Task 2: Inject the clock into Storage

**Files:**
- Modify: `crypto_farmer/storage/db.py`
- Test: `tests/unit/test_storage_clock.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_storage_clock.py
from datetime import datetime, timezone

from crypto_farmer.storage.db import Storage
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon


class _FrozenClock:
    def __init__(self, t): self._t = t
    def now(self): return self._t


def _sig():
    return Signal(
        action=SignalAction.BUY, confidence=70, reasoning="r",
        entry_price_hint=None, invalidation_level=None,
        time_horizon=TimeHorizon.SHORT, key_factors=[],
    )


def test_storage_uses_injected_clock_for_signal_timestamp(tmp_path):
    frozen = datetime(2026, 5, 17, 9, 30, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "t.db", clock=_FrozenClock(frozen))
    cid = s.start_cycle()
    sid = s.save_signal(
        cycle_id=cid, pair="BTC/USDT", timeframe="15m",
        signal=_sig(), price_at_signal=100.0, delivered=False,
    )
    row = s.get_signal_by_id(signal_id=sid)
    assert row["generated_at"].startswith("2026-05-17T09:30:00")


def test_storage_defaults_to_system_clock(tmp_path):
    # No clock passed -> behaves like before (timestamp ~ now).
    s = Storage(db_path=tmp_path / "t.db")
    cid = s.start_cycle()
    rows = s.list_recent_cycles(limit=1)
    assert rows and rows[0]["id"] == cid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_storage_clock.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'clock'`

- [ ] **Step 3: Write minimal implementation**

In `crypto_farmer/storage/db.py`, add the import near the top:

```python
from crypto_farmer.clock import Clock, SystemClock
```

Change `Storage.__init__` to accept and store a clock:

```python
    def __init__(self, *, db_path: str | Path, clock: Clock | None = None) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or SystemClock()
        self._init_schema()
```

Replace every `datetime.now(timezone.utc)` used for timestamps in `start_cycle`, `finish_cycle`, and `save_signal` with `self._clock.now()`. For example in `start_cycle`:

```python
            cur = c.execute(
                "INSERT INTO cycles (started_at) VALUES (?)",
                (_iso(self._clock.now()),),
            )
```

Apply the same `_iso(self._clock.now())` substitution in `finish_cycle` (the `finished_at` value) and `save_signal` (the `generated_at` value). Leave `save_news_items`/`save_outcome` as they are (they receive explicit datetimes).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_storage_clock.py tests/unit/test_storage.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/storage/db.py tests/unit/test_storage_clock.py
git commit -m "feat(storage): inject Clock for cycle/signal timestamps"
```

---

## Task 3: Inject the clock into OllamaClient

**Files:**
- Modify: `crypto_farmer/llm/client.py`
- Test: `tests/unit/test_llm_client_clock.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_llm_client_clock.py
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
        indicators=IndicatorSnapshot(pair="BTC/USDT"),
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
```

Note: build `IndicatorSnapshot(pair=...)` with whatever required fields it has; if it needs more, fill them with neutral values. Check `crypto_farmer/signals/models.py` for the exact schema before writing the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_llm_client_clock.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'clock'`

- [ ] **Step 3: Write minimal implementation**

In `crypto_farmer/llm/client.py` add the import:

```python
from crypto_farmer.clock import Clock, SystemClock
```

Extend `OllamaClient.__init__` to accept the clock:

```python
    def __init__(
        self, *, base_url: str, model: str,
        prompt_builder: Any,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._prompt_builder = prompt_builder
        self._timeout = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._clock = clock or SystemClock()
```

In `analyze`, render with the clock:

```python
        prompt = self._prompt_builder.render(context, now=self._clock.now())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_llm_client_clock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/llm/client.py tests/unit/test_llm_client_clock.py
git commit -m "feat(llm): render prompt with injected Clock"
```

---

## Task 4: Inject the clock into Cycle and wire it in app

**Files:**
- Modify: `crypto_farmer/cycle.py`, `crypto_farmer/app.py`
- Test: `tests/unit/test_cycle_clock.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cycle_clock.py
from datetime import datetime, timezone

from crypto_farmer.cycle import CycleDeps


def test_cycledeps_accepts_clock():
    # CycleDeps must expose a `clock` field. We only assert the dataclass field
    # exists; full integration is covered by the backtest e2e test.
    assert "clock" in CycleDeps.__dataclass_fields__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_cycle_clock.py -v`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Write minimal implementation**

In `crypto_farmer/cycle.py`:

Add import:

```python
from crypto_farmer.clock import Clock, SystemClock
```

Add a `clock` field to `CycleDeps` (give it a default so existing construction keeps working):

```python
    paper_trader: PaperTrader | None = None
    clock: Clock = field(default_factory=SystemClock)
```

Add `from dataclasses import dataclass, field` (update the existing dataclass import).

Replace the four `datetime.now(timezone.utc)` calls in `Cycle.run` with `d.clock.now()`:
- the news `since` window,
- `d.prompt_builder.render(ctx, now=...)` in `save_analysis_context`,
- the memory metadata `"timestamp"`,
- `d.outcomes.schedule_measurements(signal_id=sig_id, generated_at=...)`.

Also pass the clock instant to the paper trader so paper trades carry the historical time:

```python
            if d.paper_trader is not None and parsed.signal.confidence >= d.min_confidence:
                outcome = d.paper_trader.on_signal(
                    pair=pair, action=parsed.signal.action, price=float(price),
                    now=d.clock.now(),
                )
```

In `crypto_farmer/app.py`:

Add import `from crypto_farmer.clock import SystemClock`. Create one clock and wire it into `Storage`, `OllamaClient`, and `CycleDeps`:

```python
    clock = SystemClock()
    storage = Storage(db_path=cfg.storage.sqlite_path, clock=clock)
    ...
    llm = OllamaClient(
        base_url=cfg.llm.base_url, model=cfg.llm.model,
        prompt_builder=prompt_builder, timeout_seconds=cfg.llm.timeout_seconds,
        clock=clock,
    )
    ...
    deps = CycleDeps(
        ...,
        paper_trader=paper_trader,
        clock=clock,
    )
```

- [ ] **Step 4: Run the full suite to verify no regressions**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all existing tests + new ones)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/cycle.py crypto_farmer/app.py tests/unit/test_cycle_clock.py
git commit -m "feat(cycle): inject Clock through CycleDeps and app wiring"
```

---

## Task 5: OhlcvStore (download + cache historical candles)

**Files:**
- Create: `crypto_farmer/backtest/__init__.py` (empty)
- Create: `crypto_farmer/backtest/market.py`
- Test: `tests/unit/test_ohlcv_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ohlcv_store.py
from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import OhlcvStore


class _FakeExchange:
    """Returns 15m candles as ccxt does: [ms, o, h, l, c, v]."""
    def __init__(self, start_ms, n):
        self.calls = 0
        self._rows = [
            [start_ms + i * 900_000, 100 + i, 101 + i, 99 + i, 100 + i, 10]
            for i in range(n)
        ]
    def fetch_ohlcv(self, pair, timeframe, since=None, limit=None):
        self.calls += 1
        rows = [r for r in self._rows if r[0] >= since]
        return rows[:limit]


def test_store_loads_range_into_dataframe():
    start = datetime(2026, 5, 17, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 6, tzinfo=timezone.utc)  # 6h -> 24 candles
    ex = _FakeExchange(int(start.timestamp() * 1000), n=48)
    store = OhlcvStore(exchange=ex, page_limit=1000)
    df = store.load(pair="BTC/USDT", timeframe="15m", since=start, until=end)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["timestamp"].dt.tz is not None
    assert df["timestamp"].min() >= pd.Timestamp(start)
    assert df["timestamp"].max() <= pd.Timestamp(end)


def test_store_paginates():
    start = datetime(2026, 5, 17, tzinfo=timezone.utc)
    end = datetime(2026, 5, 18, tzinfo=timezone.utc)  # 96 candles
    ex = _FakeExchange(int(start.timestamp() * 1000), n=96)
    store = OhlcvStore(exchange=ex, page_limit=50)  # forces multiple pages
    df = store.load(pair="BTC/USDT", timeframe="15m", since=start, until=end)
    assert ex.calls >= 2
    assert len(df) >= 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ohlcv_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crypto_farmer.backtest'`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/backtest/__init__.py
```

```python
# crypto_farmer/backtest/market.py
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.clock import Clock
from crypto_farmer.signals.models import Ticker

_TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


class OhlcvStore:
    """Downloads and caches historical OHLCV for a date range, paginating ccxt."""

    def __init__(self, *, exchange, page_limit: int = 1000) -> None:
        self._ex = exchange
        self._page = page_limit

    def load(self, *, pair: str, timeframe: str, since: datetime, until: datetime) -> pd.DataFrame:
        step = _TF_MS[timeframe]
        cursor = int(since.timestamp() * 1000)
        end_ms = int(until.timestamp() * 1000)
        rows: list[list] = []
        while cursor <= end_ms:
            page = self._ex.fetch_ohlcv(pair, timeframe, since=cursor, limit=self._page)
            if not page:
                break
            rows.extend(page)
            last = page[-1][0]
            if last < cursor:  # no progress -> stop
                break
            cursor = last + step
            if len(page) < self._page and cursor > end_ms:
                break
        df = pd.DataFrame(rows, columns=_COLS).drop_duplicates(subset="timestamp")
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df[df["timestamp"] <= pd.Timestamp(until)].reset_index(drop=True)
        return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ohlcv_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/backtest/__init__.py crypto_farmer/backtest/market.py tests/unit/test_ohlcv_store.py
git commit -m "feat(backtest): OhlcvStore downloads and paginates historical candles"
```

---

## Task 6: HistoricalMarketSource

**Files:**
- Modify: `crypto_farmer/backtest/market.py`
- Test: `tests/unit/test_historical_market.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_historical_market.py
from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import HistoricalMarketSource
from crypto_farmer.clock import BacktestClock


def _df():
    base = datetime(2026, 5, 17, tzinfo=timezone.utc)
    rows = [
        {"timestamp": pd.Timestamp(base) + pd.Timedelta(minutes=15 * i),
         "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 10}
        for i in range(10)
    ]
    return pd.DataFrame(rows)


def test_fetch_ohlcv_never_returns_future_candles():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 0, 45, tzinfo=timezone.utc)  # 4th candle (i=3)
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=100)
    assert df["timestamp"].max() <= pd.Timestamp(clock.current)
    assert len(df) == 4  # candles i=0..3


def test_fetch_ohlcv_respects_lookback():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 2, 0, tzinfo=timezone.utc)  # i=8
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    df = src.fetch_ohlcv("BTC/USDT", "15m", lookback=3)
    assert len(df) == 3
    assert df["close"].iloc[-1] == 100 + 8


def test_fetch_ticker_returns_current_candle_close():
    clock = BacktestClock()
    clock.current = datetime(2026, 5, 17, 0, 30, tzinfo=timezone.utc)  # i=2
    src = HistoricalMarketSource(clock=clock, frames={"BTC/USDT": _df()})
    t = src.fetch_ticker("BTC/USDT")
    assert t.price == 100 + 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_historical_market.py -v`
Expected: FAIL with `ImportError: cannot import name 'HistoricalMarketSource'`

- [ ] **Step 3: Write minimal implementation**

Append to `crypto_farmer/backtest/market.py`:

```python
class HistoricalMarketSource:
    """MarketDataSource backed by pre-loaded frames, served up to clock.now()."""

    def __init__(self, *, clock: Clock, frames: dict[str, pd.DataFrame]) -> None:
        self._clock = clock
        self._frames = frames

    def _visible(self, pair: str) -> pd.DataFrame:
        df = self._frames[pair]
        return df[df["timestamp"] <= pd.Timestamp(self._clock.now())]

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int) -> pd.DataFrame:
        return self._visible(pair).tail(lookback).reset_index(drop=True)

    def fetch_ticker(self, pair: str) -> Ticker:
        visible = self._visible(pair)
        if visible.empty:
            raise ValueError(f"no candle for {pair} at {self._clock.now()}")
        last = visible.iloc[-1]
        return Ticker(
            pair=pair, price=float(last["close"]),
            timestamp=last["timestamp"].to_pydatetime(),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_historical_market.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/backtest/market.py tests/unit/test_historical_market.py
git commit -m "feat(backtest): HistoricalMarketSource serves candles up to clock.now()"
```

---

## Task 7: CachedLLMClient

**Files:**
- Create: `crypto_farmer/backtest/llm_cache.py`
- Test: `tests/unit/test_llm_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_llm_cache.py
from crypto_farmer.backtest.llm_cache import CachedLLMClient
from crypto_farmer.llm.client import AnalysisContext, RawLLMResponse
from crypto_farmer.signals.models import IndicatorSnapshot


class _CountingClient:
    def __init__(self): self.calls = 0
    def analyze(self, context):
        self.calls += 1
        return RawLLMResponse(text='{"hit": %d}' % self.calls)


def _ctx(pair="BTC/USDT"):
    return AnalysisContext(
        pair=pair, timeframe="15m",
        indicators=IndicatorSnapshot(pair=pair),
        ohlcv_summary={"close": 100}, news=[], memory_hits=[], recent_feedback={},
    )


def test_cache_miss_then_hit(tmp_path):
    inner = _CountingClient()
    c = CachedLLMClient(inner=inner, db_path=tmp_path / "cache.sqlite")
    r1 = c.analyze(_ctx())
    r2 = c.analyze(_ctx())  # identical context -> served from cache
    assert inner.calls == 1
    assert r1.text == r2.text


def test_cache_distinguishes_contexts(tmp_path):
    inner = _CountingClient()
    c = CachedLLMClient(inner=inner, db_path=tmp_path / "cache.sqlite")
    c.analyze(_ctx("BTC/USDT"))
    c.analyze(_ctx("ETH/USDT"))
    assert inner.calls == 2


def test_cache_persists_across_instances(tmp_path):
    db = tmp_path / "cache.sqlite"
    inner1 = _CountingClient()
    CachedLLMClient(inner=inner1, db_path=db).analyze(_ctx())
    inner2 = _CountingClient()
    CachedLLMClient(inner=inner2, db_path=db).analyze(_ctx())
    assert inner1.calls == 1
    assert inner2.calls == 0  # second instance reads from disk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_llm_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crypto_farmer.backtest.llm_cache'`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/backtest/llm_cache.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_llm_cache.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/backtest/llm_cache.py tests/unit/test_llm_cache.py
git commit -m "feat(backtest): CachedLLMClient keyed by analysis context"
```

---

## Task 8: NullNotifier

**Files:**
- Create: `crypto_farmer/backtest/null_notifier.py`
- Test: `tests/unit/test_null_notifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_null_notifier.py
from crypto_farmer.backtest.null_notifier import NullNotifier
from crypto_farmer.signals.models import CycleStatus
from crypto_farmer.paper.models import ActionKind, ActionOutcome


def test_null_notifier_is_silent_noop():
    n = NullNotifier()
    # None of these must raise or do anything observable.
    n.deliver([])
    n.deliver_cycle_status(status=CycleStatus.OK, note=None)
    n.deliver_paper_outcome(ActionOutcome(kind=ActionKind.IGNORED_HOLD, pair="X/USDT"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_null_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/backtest/null_notifier.py
from __future__ import annotations

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.paper.models import ActionOutcome
from crypto_farmer.signals.models import CycleStatus


class NullNotifier:
    """Notifier that does nothing — backtests must not spam Telegram."""

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        pass

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        pass

    def deliver_paper_outcome(self, outcome: ActionOutcome) -> None:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_null_notifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/backtest/null_notifier.py tests/unit/test_null_notifier.py
git commit -m "feat(backtest): NullNotifier no-op for offline runs"
```

---

## Task 9: BacktestRunner (builder + loop)

**Files:**
- Create: `crypto_farmer/backtest/runner.py`
- Test: `tests/integration/test_backtest_e2e.py`

This task builds the deps with backtest variants and runs the candle loop end to end. The test injects fakes (no Ollama, no network).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_backtest_e2e.py
from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.backtest.market import HistoricalMarketSource
from crypto_farmer.backtest.runner import BacktestRunner, candle_times
from crypto_farmer.clock import BacktestClock
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.backtest.null_notifier import NullNotifier
from crypto_farmer.llm.client import RawLLMResponse
from crypto_farmer.metrics import Metrics
from crypto_farmer.storage.db import Storage


def test_candle_times_15m():
    start = datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
    ts = candle_times(start, end, "15m")
    assert ts[0] == start
    assert ts[-1] == end
    assert len(ts) == 5  # 0:00,0:15,0:30,0:45,1:00


def _trending_df(n=120):
    base = datetime(2026, 5, 17, tzinfo=timezone.utc)
    rows = [
        {"timestamp": pd.Timestamp(base) + pd.Timedelta(minutes=15 * i),
         "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 100 + (i % 5)}
        for i in range(n)
    ]
    return pd.DataFrame(rows)


class _AlwaysHoldLLM:
    """Deterministic fake: always returns a valid HOLD signal."""
    def analyze(self, context):
        return RawLLMResponse(text='{"action":"HOLD","confidence":50,'
                                   '"reasoning":"r","time_horizon":"short","key_factors":[]}')


class _FakeEmbeddings:
    def embed(self, text): return [0.0, 0.0, 0.0]


def test_backtest_runs_and_isolates_data(tmp_path, monkeypatch):
    """A short backtest with a fake LLM produces cycles in an isolated DB and
    never touches the live data dir."""
    clock = BacktestClock()
    frames = {"BTC/USDT": _trending_df()}
    run_dir = tmp_path / "run"
    storage = Storage(db_path=run_dir / "bt.db", clock=clock)
    market = HistoricalMarketSource(clock=clock, frames=frames)

    runner = BacktestRunner.for_test(
        clock=clock, storage=storage, market=market,
        llm_client=_AlwaysHoldLLM(), embeddings=_FakeEmbeddings(),
        notifier=NullNotifier(), metrics=Metrics(),
        pairs=["BTC/USDT"], chroma_dir=run_dir / "chroma",
    )

    start = datetime(2026, 5, 17, 6, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 17, 7, 0, tzinfo=timezone.utc)
    runner.run(since=start, until=end)

    cycles = storage.list_recent_cycles(limit=100)
    assert len(cycles) == 5  # one per 15m candle in [6:00, 7:00]
    assert all(c["status"] in ("ok", "degraded") for c in cycles)
```

Before writing the implementation, confirm the exact field names/values required by `Signal`/`IndicatorEngine` in `crypto_farmer/signals/models.py` and `crypto_farmer/analysis/indicators.py`; the trending dataframe must have enough rows (≥ the indicator warmup, e.g. ≥ 50) for `IndicatorEngine.compute` not to raise. `_trending_df(n=120)` covers this.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_backtest_e2e.py -v`
Expected: FAIL with `ImportError: cannot import name 'BacktestRunner'`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/backtest/runner.py
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter, PrefilterConfig
from crypto_farmer.backtest.market import HistoricalMarketSource, OhlcvStore
from crypto_farmer.clock import BacktestClock
from crypto_farmer.cycle import Cycle, CycleDeps
from crypto_farmer.data.news import NoopNewsSource
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import ChromaMemory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.storage.db import Storage

log = get_logger(__name__)

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def candle_times(since: datetime, until: datetime, timeframe: str) -> list[datetime]:
    step = timedelta(minutes=_TF_MINUTES[timeframe])
    out, t = [], since
    while t <= until:
        out.append(t)
        t += step
    return out


class BacktestRunner:
    def __init__(self, *, clock: BacktestClock, cycle: Cycle, outcomes: OutcomeService,
                 timeframe: str) -> None:
        self._clock = clock
        self._cycle = cycle
        self._outcomes = outcomes
        self._tf = timeframe

    @classmethod
    def for_test(cls, *, clock, storage, market, llm_client, embeddings, notifier,
                 metrics, pairs, chroma_dir, timeframe="15m") -> "BacktestRunner":
        """Build a runner from injected components (used by tests and the CLI builder)."""
        from crypto_farmer.llm.parser import SignalParser
        from crypto_farmer.llm.prompts import PromptBuilder

        memory = ChromaMemory(persist_dir=str(chroma_dir), collection_name="bt")
        prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
        parser = SignalParser(llm_client=llm_client, max_retries=0)
        feedback = FeedbackBuilder(storage=storage)
        outcomes = OutcomeService(
            storage=storage, market=market,
            horizons_hours=[1, 4, 24], memory=memory,
        )
        prefilter = Prefilter(PrefilterConfig(
            rsi_oversold=30, rsi_overbought=70, volume_anomaly_factor=1.8,
            atr_expansion_factor=1.5, cooldown_minutes=0,
        ))
        deps = CycleDeps(
            market=market, news=NoopNewsSource(),
            indicators=IndicatorEngine(), prefilter=prefilter,
            prompt_builder=prompt_builder, parser=parser,
            embeddings=embeddings, memory=memory,
            feedback=feedback, outcomes=outcomes,
            notifier=notifier, storage=storage, metrics=metrics,
            pairs=pairs, timeframe=timeframe, ohlcv_lookback=200,
            min_confidence=60, news_max_age_hours=24,
            memory_k=3, feedback_lookback=20,
            paper_trader=None, clock=clock,
        )
        return cls(clock=clock, cycle=Cycle(deps), outcomes=outcomes, timeframe=timeframe)

    def run(self, *, since: datetime, until: datetime) -> None:
        for t in candle_times(since, until, self._tf):
            self._clock.current = t
            self._cycle.run()
            self._outcomes.run_due_jobs(now=t)
        # Drain outcomes for the 24h after `until` using the future candles.
        drain_end = until + timedelta(hours=24)
        for t in candle_times(until, drain_end, self._tf):
            self._clock.current = t
            self._outcomes.run_due_jobs(now=t)
        log.info("backtest_finished", extra={"since": since.isoformat(), "until": until.isoformat()})
```

Notes for the implementer:
- `Prefilter`/`PrefilterConfig` field names must match `crypto_farmer/analysis/prefilter.py`; copy them exactly. The values above mirror the defaults used in `app.py`.
- `ChromaMemory.__init__` signature must match `crypto_farmer/learning/memory.py` (`persist_dir`, `collection_name`). Verify before running.
- If `IndicatorEngine.compute` needs the dataframe to carry enough rows, the e2e test's `_trending_df(n=120)` provides them; the backtest's real `OhlcvStore` must therefore download a `lookback`-sized margin before `since` (handled in Task 11).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_backtest_e2e.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add crypto_farmer/backtest/runner.py tests/integration/test_backtest_e2e.py
git commit -m "feat(backtest): BacktestRunner replays the cycle over a date range"
```

---

## Task 10: BacktestReport

**Files:**
- Create: `crypto_farmer/backtest/report.py`
- Test: `tests/unit/test_backtest_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_backtest_report.py
from datetime import datetime, timezone

from crypto_farmer.backtest.report import build_report
from crypto_farmer.storage.db import Storage
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon


class _FrozenClock:
    def __init__(self, t): self._t = t
    def now(self): return self._t


def _sig(action):
    return Signal(action=action, confidence=70, reasoning="r",
                  entry_price_hint=None, invalidation_level=None,
                  time_horizon=TimeHorizon.SHORT, key_factors=[])


def test_report_counts_signals_and_winrate(tmp_path):
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db", clock=_FrozenClock(t))
    cid = s.start_cycle()
    sid = s.save_signal(cycle_id=cid, pair="BTC/USDT", timeframe="15m",
                        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True)
    s.save_outcome(signal_id=sid, horizon="4h", measured_at=t,
                   price_then=105.0, return_pct=5.0, verdict="correct")

    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 1" in text
    assert "BUY" in text
    assert "4h: 100% (1/1)" in text


def test_report_handles_empty(tmp_path):
    t = datetime(2026, 5, 17, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db", clock=_FrozenClock(t))
    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 0" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_report.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# crypto_farmer/backtest/report.py
from __future__ import annotations

from datetime import datetime

from crypto_farmer.storage.db import Storage


def build_report(*, storage: Storage, since: datetime, until: datetime) -> str:
    signals = storage.list_recent_signals(limit=100000)
    actions: dict[str, int] = {}
    for s in signals:
        actions[s["action"]] = actions.get(s["action"], 0) + 1

    wins = {"1h": 0, "4h": 0, "24h": 0}
    rated = {"1h": 0, "4h": 0, "24h": 0}
    for s in signals:
        for o in storage.list_outcomes_for_signal(s["id"]):
            h = o["horizon"]
            if h in rated:
                rated[h] += 1
                if o.get("verdict") == "correct":
                    wins[h] += 1

    def wr(h: str) -> str:
        return f"{round(100 * wins[h] / rated[h])}% ({wins[h]}/{rated[h]})" if rated[h] else "—"

    dist = ", ".join(f"{a}={n}" for a, n in actions.items()) or "—"
    lines = [
        f"# Backtest {since.date()} → {until.date()}",
        f"Señales: {len(signals)}. Distribución: {dist}",
        f"Win rate 1h: {wr('1h')}  ·  4h: {wr('4h')}  ·  24h: {wr('24h')}",
    ]

    wallet = storage.get_wallet()
    if wallet is not None:
        trades = storage.list_trades(limit=100000)
        total_pnl = sum(float(t["net_profit"]) for t in trades)
        wins_n = sum(1 for t in trades if float(t["net_profit"]) > 0)
        lines += [
            "",
            "## Paper trading",
            f"P&L: {total_pnl:+.2f}€  ·  Trades: {len(trades)} "
            f"(ganadores {wins_n}/{len(trades)})  ·  "
            f"Cash {float(wallet['cash']):.2f}€  ·  Vault {float(wallet['vault']):.2f}€  ·  "
            f"Bancarrotas {wallet['bankruptcies']}",
        ]
    return "\n".join(lines)
```

Note: the HODL benchmark and max-drawdown lines are added in Task 12 (they need the OHLCV frames and the trade time series); this task ships the core report.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_report.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add crypto_farmer/backtest/report.py tests/unit/test_backtest_report.py
git commit -m "feat(backtest): core performance report"
```

---

## Task 11: Production builder + CLI command

**Files:**
- Modify: `crypto_farmer/backtest/runner.py` (add `build_from_config`)
- Modify: `crypto_farmer/__main__.py` (add `backtest` subcommand)
- Test: `tests/unit/test_backtest_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_backtest_cli.py
from datetime import datetime

from crypto_farmer.__main__ import _parse_backtest_args


def test_parse_backtest_args():
    ns = _parse_backtest_args(["--from", "2026-05-17", "--to", "2026-05-22",
                               "--pairs", "BTC/USDT,ETH/USDT"])
    assert ns.date_from == datetime(2026, 5, 17)
    assert ns.date_to == datetime(2026, 5, 22)
    assert ns.pairs == ["BTC/USDT", "ETH/USDT"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_cli.py -v`
Expected: FAIL with `ImportError: cannot import name '_parse_backtest_args'`

- [ ] **Step 3: Write minimal implementation**

In `crypto_farmer/backtest/runner.py`, add a config-driven builder that wires the **real** Ollama LLM (wrapped in the cache), the historical market source from `OhlcvStore`, isolated storage/chroma, and an optional paper trader. Use `BacktestRunner.for_test` internally but with real components:

```python
def build_from_config(*, config, run_dir: Path, pairs: list[str],
                      since: datetime, until: datetime) -> "BacktestRunner":
    import ccxt
    from crypto_farmer.backtest.llm_cache import CachedLLMClient
    from crypto_farmer.backtest.null_notifier import NullNotifier
    from crypto_farmer.llm.client import OllamaClient
    from crypto_farmer.llm.prompts import PromptBuilder
    from crypto_farmer.learning.embeddings import OllamaEmbeddings
    from crypto_farmer.paper.trader import PaperTrader, PaperTraderConfig

    run_dir.mkdir(parents=True, exist_ok=True)
    clock = BacktestClock()
    storage = Storage(db_path=str(run_dir / "crypto_farmer.db"), clock=clock)

    tf = config.market.timeframe
    lookback = config.market.ohlcv_lookback
    margin = timedelta(minutes=_TF_MINUTES[tf] * lookback)
    store = OhlcvStore(exchange=ccxt.binance({"enableRateLimit": True}))
    frames = {
        p: store.load(pair=p, timeframe=tf, since=since - margin, until=until + timedelta(hours=24))
        for p in pairs
    }
    market = HistoricalMarketSource(clock=clock, frames=frames)

    prompt_builder = PromptBuilder(template_path="config/prompts/analyze_pair.j2")
    inner = OllamaClient(
        base_url=config.llm.base_url, model=config.llm.model,
        prompt_builder=prompt_builder, timeout_seconds=config.llm.timeout_seconds,
        clock=clock,
    )
    cached = CachedLLMClient(inner=inner, db_path="data/backtest/llm_cache.sqlite")
    embeddings = OllamaEmbeddings(base_url=config.llm.base_url, model=config.llm.embedding_model)

    paper = None
    if config.paper.enabled:
        paper = PaperTrader(storage=storage, config=PaperTraderConfig(
            initial_cash=config.paper.initial_cash,
            position_size_pct=config.paper.position_size_pct,
            vault_pct=config.paper.vault_pct, fee_rate=config.paper.fee_rate,
        ))

    runner = BacktestRunner.for_test(
        clock=clock, storage=storage, market=market,
        llm_client=cached, embeddings=embeddings, notifier=NullNotifier(),
        metrics=Metrics(), pairs=pairs, chroma_dir=run_dir / "chroma", timeframe=tf,
    )
    # Attach the paper trader (for_test builds deps without one).
    runner._cycle._deps.paper_trader = paper  # noqa: SLF001 - explicit backtest wiring
    runner._storage = storage
    return runner
```

Add `self._storage = ...` storage reference in `__init__` (set `self._storage = None`) so `build_from_config` can attach it for the report. Adjust `BacktestRunner.for_test` to also set `runner._storage = storage`.

In `crypto_farmer/__main__.py`, add the subcommand. Add an argument parser helper and a `backtest` branch in `main`:

```python
def _parse_backtest_args(argv):
    import argparse
    p = argparse.ArgumentParser(prog="crypto-farmer backtest")
    p.add_argument("--from", dest="date_from", required=True,
                   type=lambda s: __import__("datetime").datetime.fromisoformat(s))
    p.add_argument("--to", dest="date_to", required=True,
                   type=lambda s: __import__("datetime").datetime.fromisoformat(s))
    p.add_argument("--pairs", default=None,
                   type=lambda s: [x.strip() for x in s.split(",")])
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--export-rag", action="store_true")
    return p.parse_args(argv)
```

Wire it into `main()`: if the first CLI arg is `backtest`, dispatch to a `_run_backtest(argv)` function that loads config, resolves `pairs` (default `cfg.market.pairs`), builds the runner with `build_from_config`, runs it, writes `build_report(...)` to `run_dir/report.md`, prints it, and (if `--export-rag`) copies the chroma collection into the live RAG. Use a `run_id` like `f"{date_from:%Y%m%d}_{date_to:%Y%m%d}__{datetime.now():%Y%m%d-%H%M%S}"` under `data/backtest/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add crypto_farmer/backtest/runner.py crypto_farmer/__main__.py tests/unit/test_backtest_cli.py
git commit -m "feat(backtest): config-driven builder and 'backtest' CLI command"
```

---

## Task 12: HODL benchmark + max drawdown in report

**Files:**
- Modify: `crypto_farmer/backtest/report.py`
- Test: `tests/unit/test_backtest_report.py` (add cases)

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_backtest_report.py
import pandas as pd
from crypto_farmer.backtest.report import hodl_return_pct, max_drawdown_pct


def test_hodl_return_equal_weight():
    base = pd.Timestamp("2026-05-17", tz="UTC")
    df = pd.DataFrame([
        {"timestamp": base, "open": 0, "high": 0, "low": 0, "close": 100, "volume": 1},
        {"timestamp": base + pd.Timedelta(hours=1), "open": 0, "high": 0, "low": 0, "close": 110, "volume": 1},
    ])
    # +10% on a single pair held start->end
    assert round(hodl_return_pct({"BTC/USDT": df}), 2) == 10.0


def test_max_drawdown():
    equity = [1000, 1100, 900, 950]  # peak 1100 -> trough 900 = -18.18%
    assert round(max_drawdown_pct(equity), 2) == -18.18
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'hodl_return_pct'`

- [ ] **Step 3: Write minimal implementation**

Add to `crypto_farmer/backtest/report.py`:

```python
import pandas as pd


def hodl_return_pct(frames: dict[str, "pd.DataFrame"]) -> float:
    """Equal-weight buy-at-first-candle, hold-to-last-candle return, in %."""
    rets = []
    for df in frames.values():
        if len(df) >= 2:
            first = float(df["close"].iloc[0])
            last = float(df["close"].iloc[-1])
            if first > 0:
                rets.append((last / first - 1.0) * 100.0)
    return sum(rets) / len(rets) if rets else 0.0


def max_drawdown_pct(equity: list[float]) -> float:
    """Worst peak-to-trough drop of an equity series, in % (<= 0)."""
    peak = float("-inf")
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, (v - peak) / peak * 100.0)
    return round(worst, 2)
```

Then extend `build_report` to accept an optional `frames` argument and append a `HODL: {hodl_return_pct(frames):+.2f}%` line plus a `Max drawdown` line computed from the running paper-equity (cash+vault after each trade). Keep the existing signature working by defaulting `frames=None` (skip the HODL line when not provided).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_backtest_report.py -v`
Expected: PASS (all)

- [ ] **Step 5: Wire frames into the CLI report call**

In `_run_backtest` (Task 11), pass the loaded `frames` to `build_report(..., frames=frames)`.

- [ ] **Step 6: Commit**

```bash
git add crypto_farmer/backtest/report.py crypto_farmer/__main__.py tests/unit/test_backtest_report.py
git commit -m "feat(backtest): HODL benchmark and max drawdown in report"
```

---

## Task 13: Manual smoke test (real run, short range)

**Files:** none (manual verification)

- [ ] **Step 1: Run a tiny real backtest**

Run:
```bash
.venv/Scripts/python.exe -m crypto_farmer backtest --from 2026-05-20 --to 2026-05-21 --pairs BTC/USDT
```
Expected: downloads candles, runs (first pass slow due to Ollama), writes `data/backtest/<run_id>/report.md`, prints the report. The live `data/crypto_farmer.db` and `data/chroma/` are untouched.

- [ ] **Step 2: Re-run the same range and confirm the cache makes it fast**

Run the same command again.
Expected: noticeably faster (LLM responses served from `data/backtest/llm_cache.sqlite`); same numbers.

- [ ] **Step 3: Confirm isolation**

Run: `.venv/Scripts/python.exe -c "import os; print(os.path.getmtime('data/crypto_farmer.db'))"` before and after a backtest.
Expected: unchanged — the live DB is never written by a backtest.

---

## Self-review notes

- **Spec coverage:** Clock (T1–T4), HistoricalMarketSource/OhlcvStore (T5–T6), CachedLLMClient (T7), isolation (T9/T11 run_dir + separate Storage/Chroma), NullNotifier so no Telegram (T8), runner loop + outcome drain (T9), report incl. HODL + drawdown (T10/T12), CLI with `--from/--to/--pairs/--export-rag` (T11). All spec sections map to a task.
- **`--export-rag`** is parsed in T11 and its copy step is described in T11 Step 3 (copy the run's chroma collection into the live RAG); ship the flag even if the copy is a thin helper.
- **Verify-before-code reminders** are embedded where a signature must be confirmed against existing code (`IndicatorSnapshot`, `Prefilter`, `ChromaMemory`, `Signal`).
- **No production behavior change in live mode:** every injected clock defaults to `SystemClock`, and Task 4 Step 4 runs the full suite to prove it.
