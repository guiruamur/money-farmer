from crypto_farmer.backtest.null_notifier import NullNotifier
from crypto_farmer.signals.models import CycleStatus
from crypto_farmer.paper.models import ActionKind, ActionOutcome


def test_null_notifier_is_silent_noop():
    n = NullNotifier()
    n.deliver([])
    n.deliver_cycle_status(status=CycleStatus.OK, note=None)
    n.deliver_paper_outcome(ActionOutcome(kind=ActionKind.IGNORED_HOLD, pair="X/USDT"))
