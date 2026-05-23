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
