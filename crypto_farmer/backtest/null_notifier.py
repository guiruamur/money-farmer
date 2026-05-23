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
