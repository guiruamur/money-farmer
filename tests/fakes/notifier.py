from __future__ import annotations

from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import CycleStatus


class FakeNotifier:
    def __init__(self) -> None:
        self.delivered: list[DeliverableSignal] = []
        self.cycle_notes: list[tuple[CycleStatus, str | None]] = []

    def deliver(self, signals: list[DeliverableSignal]) -> None:
        self.delivered.extend(signals)

    def deliver_cycle_status(self, *, status: CycleStatus, note: str | None) -> None:
        self.cycle_notes.append((status, note))
