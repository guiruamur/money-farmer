from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crypto_farmer.signals.models import CycleStatus, Signal


@dataclass
class DeliverableSignal:
    pair: str
    signal: Signal
    price_at_signal: float


class Notifier(Protocol):
    def deliver(self, signals: list[DeliverableSignal]) -> None: ...
    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None: ...
