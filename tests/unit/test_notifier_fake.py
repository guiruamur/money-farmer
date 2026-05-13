from crypto_farmer.delivery.notifier import DeliverableSignal
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon
from tests.fakes.notifier import FakeNotifier


def _ds() -> DeliverableSignal:
    return DeliverableSignal(
        pair="BTC/USDT",
        signal=Signal(
            action=SignalAction.BUY, confidence=72, reasoning="r",
            entry_price_hint=100.0, invalidation_level=95.0,
            time_horizon=TimeHorizon.SHORT, key_factors=["k"],
        ),
        price_at_signal=100.0,
    )


def test_fake_notifier_records_delivered():
    n = FakeNotifier()
    n.deliver([_ds()])
    assert len(n.delivered) == 1
    assert n.delivered[0].pair == "BTC/USDT"
