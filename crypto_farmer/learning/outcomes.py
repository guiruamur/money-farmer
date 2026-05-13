from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from crypto_farmer.data.market import MarketDataSource, MarketFetchError
from crypto_farmer.learning.memory import Memory
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.signals.models import SignalAction
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


def _verdict(action: str, return_pct: float, *, threshold: float = 0.5) -> str:
    if abs(return_pct) < threshold:
        return "neutral"
    if action == SignalAction.BUY.value:
        return "correct" if return_pct > 0 else "incorrect"
    if action == SignalAction.SELL.value:
        return "correct" if return_pct < 0 else "incorrect"
    return "neutral"  # HOLD


class OutcomeService:
    MAX_STALE_HOURS = 48

    def __init__(
        self, *, storage: Storage, market: MarketDataSource,
        horizons_hours: Iterable[int], memory: Memory | None,
    ) -> None:
        self._storage = storage
        self._market = market
        self._horizons = list(horizons_hours)
        self._memory = memory

    def schedule_measurements(
        self, *, signal_id: int, generated_at: datetime
    ) -> None:
        for h in self._horizons:
            due = generated_at + timedelta(hours=h)
            self._storage.enqueue_outcome_job(
                signal_id=signal_id, horizon=f"{h}h", due_at=due,
            )

    def run_due_jobs(self, *, now: datetime) -> int:
        jobs = self._storage.list_due_outcome_jobs(now=now)
        measured = 0
        for job in jobs:
            due_at = datetime.fromisoformat(job["due_at"].replace("Z", "+00:00"))
            if (now - due_at) > timedelta(hours=self.MAX_STALE_HOURS):
                self._storage.mark_outcome_job_done(job_id=job["id"])
                log.info("outcome_job_stale_discarded", extra={"job_id": job["id"]})
                continue
            try:
                self._measure(job, now=now)
                measured += 1
            except MarketFetchError as e:
                log.warning("outcome_market_fetch_failed",
                            extra={"job_id": job["id"], "error": str(e)})
                # No marcar done: reintentar al siguiente ciclo
                continue
            self._storage.mark_outcome_job_done(job_id=job["id"])
        return measured

    def _measure(self, job: dict, *, now: datetime) -> None:
        sig_id = job["signal_id"]
        sig_row = self._storage.get_signal_by_id(signal_id=sig_id)
        if sig_row is None:
            return
        ticker = self._market.fetch_ticker(sig_row["pair"])
        price_now = ticker.price
        entry_price = float(sig_row["price_at_signal"])
        return_pct = (price_now - entry_price) / entry_price * 100.0
        verdict = _verdict(sig_row["action"], return_pct)
        self._storage.save_outcome(
            signal_id=sig_id, horizon=job["horizon"],
            measured_at=now, price_then=price_now,
            return_pct=return_pct, verdict=verdict,
        )
        if self._memory is not None and job["horizon"] in ("4h", "24h"):
            mem_entry_id = sig_row.get("memory_entry_id")
            if mem_entry_id:
                kwargs = (
                    {"return_4h": return_pct}
                    if job["horizon"] == "4h"
                    else {"return_24h": return_pct}
                )
                self._memory.update_outcome(entry_id=mem_entry_id, **kwargs)
                log.debug(
                    "memory_outcome_updated",
                    extra={"signal_id": sig_id, "horizon": job["horizon"], "entry_id": mem_entry_id},
                )
