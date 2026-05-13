from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from crypto_farmer.logging_setup import get_logger


log = get_logger(__name__)


class CycleScheduler:
    def __init__(
        self, *, interval_minutes: int, timezone: str,
        cycle_callable: Callable[[], None], outcomes_callable: Callable[[], None],
        digest_callable: Callable[[], None] | None = None,
        digest_minutes: int = 0,
    ) -> None:
        self._scheduler = BackgroundScheduler(timezone=timezone)
        self._scheduler.add_job(
            cycle_callable, trigger="interval",
            minutes=interval_minutes, id="cycle",
            max_instances=1, coalesce=True,
        )
        self._scheduler.add_job(
            outcomes_callable, trigger="interval",
            minutes=max(1, interval_minutes // 3), id="outcomes",
            max_instances=1, coalesce=True,
        )
        if digest_callable is not None and digest_minutes > 0:
            self._scheduler.add_job(
                digest_callable, trigger="interval",
                minutes=digest_minutes, id="digest",
                max_instances=1, coalesce=True,
            )
        self._paused = False

    def start(self) -> None:
        self._scheduler.start()
        log.info("scheduler_started")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")

    def pause(self) -> None:
        self._scheduler.pause()
        self._paused = True
        log.info("scheduler_paused")

    def resume(self) -> None:
        self._scheduler.resume()
        self._paused = False
        log.info("scheduler_resumed")

    def is_running(self) -> bool:
        return self._scheduler.running

    def is_paused(self) -> bool:
        return self._paused
