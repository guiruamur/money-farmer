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
