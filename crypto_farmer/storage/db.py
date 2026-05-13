from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from crypto_farmer.signals.models import CycleStatus, NewsItem, Signal


SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  pairs_analyzed INTEGER DEFAULT 0,
  pairs_passed_prefilter INTEGER DEFAULT 0,
  signals_generated INTEGER DEFAULT 0,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cycle_id INTEGER NOT NULL REFERENCES cycles(id),
  pair TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  action TEXT NOT NULL,
  confidence INTEGER NOT NULL,
  reasoning TEXT,
  entry_price_hint REAL,
  invalidation_level REAL,
  time_horizon TEXT,
  key_factors_json TEXT,
  delivered INTEGER NOT NULL DEFAULT 0,
  price_at_signal REAL,
  memory_entry_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals(pair);
CREATE INDEX IF NOT EXISTS idx_signals_generated ON signals(generated_at);

CREATE TABLE IF NOT EXISTS signal_outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL REFERENCES signals(id),
  horizon TEXT NOT NULL,
  measured_at TEXT NOT NULL,
  price_then REAL,
  return_pct REAL,
  verdict TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal ON signal_outcomes(signal_id);

CREATE TABLE IF NOT EXISTS analysis_contexts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL UNIQUE REFERENCES signals(id),
  indicators_json TEXT,
  news_json TEXT,
  memory_hits_json TEXT,
  feedback_summary TEXT,
  prompt_rendered TEXT,
  raw_llm_response TEXT
);

CREATE TABLE IF NOT EXISTS news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  body TEXT,
  published_at TEXT,
  fetched_at TEXT,
  related_pairs_json TEXT
);

CREATE TABLE IF NOT EXISTS outcome_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL REFERENCES signals(id),
  horizon TEXT NOT NULL,
  due_at TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON outcome_jobs(due_at, done);

CREATE TABLE IF NOT EXISTS paper_wallet (
  id INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
  cash REAL NOT NULL,
  vault REAL NOT NULL,
  bankruptcies INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT NOT NULL UNIQUE,
  qty REAL NOT NULL,
  avg_entry_price REAL NOT NULL,
  opened_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT NOT NULL,
  qty REAL NOT NULL,
  entry_price REAL NOT NULL,
  exit_price REAL NOT NULL,
  gross_profit REAL NOT NULL,
  fees REAL NOT NULL,
  net_profit REAL NOT NULL,
  to_vault REAL NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_closed ON paper_trades(closed_at);
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Storage:
    def __init__(self, *, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)
            # Graceful migration for existing DBs that predate the memory_entry_id column.
            try:
                c.execute("ALTER TABLE signals ADD COLUMN memory_entry_id TEXT")
            except Exception:
                pass  # Column already exists (OperationalError) or other benign error.

    def start_cycle(self) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO cycles (started_at) VALUES (?)",
                (_iso(datetime.now(timezone.utc)),),
            )
            return int(cur.lastrowid)

    def finish_cycle(
        self, cycle_id: int, *, status: CycleStatus,
        pairs_analyzed: int, pairs_passed_prefilter: int,
        signals_generated: int, notes: str | None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE cycles SET finished_at=?, status=?, pairs_analyzed=?, "
                "pairs_passed_prefilter=?, signals_generated=?, notes=? WHERE id=?",
                (_iso(datetime.now(timezone.utc)), status.value,
                 pairs_analyzed, pairs_passed_prefilter, signals_generated, notes, cycle_id),
            )

    def save_signal(
        self, *, cycle_id: int, pair: str, timeframe: str,
        signal: Signal, price_at_signal: float, delivered: bool,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO signals (cycle_id, pair, timeframe, generated_at, action, "
                "confidence, reasoning, entry_price_hint, invalidation_level, time_horizon, "
                "key_factors_json, delivered, price_at_signal) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cycle_id, pair, timeframe, _iso(datetime.now(timezone.utc)),
                 signal.action.value, signal.confidence, signal.reasoning,
                 signal.entry_price_hint, signal.invalidation_level,
                 signal.time_horizon.value, json.dumps(signal.key_factors),
                 1 if delivered else 0, price_at_signal),
            )
            return int(cur.lastrowid)

    def save_outcome(
        self, *, signal_id: int, horizon: str, measured_at: datetime,
        price_then: float, return_pct: float, verdict: str,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO signal_outcomes (signal_id, horizon, measured_at, "
                "price_then, return_pct, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                (signal_id, horizon, _iso(measured_at), price_then, return_pct, verdict),
            )

    def list_outcomes_for_signal(self, signal_id: int) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM signal_outcomes WHERE signal_id=? ORDER BY measured_at",
                (signal_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_recent_cycles(self, *, limit: int) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def list_recent_signals(self, *, limit: int, pair: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if pair:
                cur = c.execute(
                    "SELECT * FROM signals WHERE pair=? ORDER BY id DESC LIMIT ?",
                    (pair, limit),
                )
            else:
                cur = c.execute(
                    "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
                )
            return [dict(r) for r in cur.fetchall()]

    def last_signal_for_pair(self, pair: str) -> dict[str, Any] | None:
        rows = self.list_recent_signals(limit=1, pair=pair)
        return rows[0] if rows else None

    def get_signal_by_id(self, *, signal_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM signals WHERE id=?", (signal_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_signal_memory_entry_id(self, *, signal_id: int, memory_entry_id: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE signals SET memory_entry_id=? WHERE id=?",
                (memory_entry_id, signal_id),
            )

    def save_news_items(self, items: list[NewsItem]) -> int:
        if not items:
            return 0
        with self._conn() as c:
            inserted = 0
            for n in items:
                try:
                    c.execute(
                        "INSERT INTO news_items (source, url, title, body, "
                        "published_at, fetched_at, related_pairs_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (n.source, n.url, n.title, n.body, _iso(n.published_at),
                         _iso(datetime.now(timezone.utc)),
                         json.dumps(n.related_pairs)),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue
            return inserted

    def list_news_since(self, since: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM news_items WHERE published_at >= ? ORDER BY published_at DESC",
                (_iso(since),),
            )
            return [dict(r) for r in cur.fetchall()]

    def save_analysis_context(
        self, *, signal_id: int, indicators: dict, news: list,
        memory_hits: list, feedback_summary: str,
        prompt_rendered: str, raw_llm_response: str,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO analysis_contexts (signal_id, indicators_json, news_json, "
                "memory_hits_json, feedback_summary, prompt_rendered, raw_llm_response) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (signal_id, json.dumps(indicators), json.dumps(news),
                 json.dumps(memory_hits), feedback_summary,
                 prompt_rendered, raw_llm_response),
            )

    def get_analysis_context(self, signal_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM analysis_contexts WHERE signal_id=?", (signal_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def enqueue_outcome_job(
        self, *, signal_id: int, horizon: str, due_at: datetime
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO outcome_jobs (signal_id, horizon, due_at) VALUES (?, ?, ?)",
                (signal_id, horizon, _iso(due_at)),
            )

    def list_due_outcome_jobs(self, *, now: datetime) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM outcome_jobs WHERE done=0 AND due_at<=? ORDER BY due_at",
                (_iso(now),),
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_outcome_job_done(self, *, job_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE outcome_jobs SET done=1 WHERE id=?", (job_id,))

    # ---------- Paper trading ----------

    def get_wallet(self) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM paper_wallet WHERE id=1")
            row = cur.fetchone()
            return dict(row) if row else None

    def save_wallet(self, *, cash: float, vault: float, bankruptcies: int) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO paper_wallet (id, cash, vault, bankruptcies, updated_at) "
                "VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET cash=excluded.cash, vault=excluded.vault, "
                "bankruptcies=excluded.bankruptcies, updated_at=excluded.updated_at",
                (cash, vault, bankruptcies, _iso(datetime.now(timezone.utc))),
            )

    def upsert_position(
        self, *, pair: str, qty: float, avg_entry_price: float, opened_at: datetime
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO paper_positions (pair, qty, avg_entry_price, opened_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(pair) DO UPDATE SET qty=excluded.qty, "
                "avg_entry_price=excluded.avg_entry_price, opened_at=excluded.opened_at "
                "RETURNING id",
                (pair, qty, avg_entry_price, _iso(opened_at)),
            )
            row = cur.fetchone()
            return int(row["id"]) if row else 0

    def get_position(self, *, pair: str) -> dict[str, Any] | None:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM paper_positions WHERE pair=?", (pair,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_position(self, *, pair: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM paper_positions WHERE pair=?", (pair,))

    def list_positions(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM paper_positions ORDER BY pair")
            return [dict(r) for r in cur.fetchall()]

    def delete_all_positions(self) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM paper_positions")
            return cur.rowcount

    def save_trade(
        self, *, pair: str, qty: float, entry_price: float, exit_price: float,
        gross_profit: float, fees: float, net_profit: float, to_vault: float,
        opened_at: datetime, closed_at: datetime,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO paper_trades (pair, qty, entry_price, exit_price, "
                "gross_profit, fees, net_profit, to_vault, opened_at, closed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pair, qty, entry_price, exit_price, gross_profit, fees, net_profit,
                 to_vault, _iso(opened_at), _iso(closed_at)),
            )
            return int(cur.lastrowid)

    def list_trades(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]
