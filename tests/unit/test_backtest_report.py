from datetime import datetime, timedelta, timezone

import pandas as pd

from crypto_farmer.backtest.report import build_report, hodl_return_pct, max_drawdown_pct
from crypto_farmer.storage.db import Storage
from crypto_farmer.signals.models import Signal, SignalAction, TimeHorizon


def _sig(action):
    return Signal(action=action, confidence=70, reasoning="r",
                  entry_price_hint=None, invalidation_level=None,
                  time_horizon=TimeHorizon.SHORT, key_factors=[])


def test_report_counts_signals_and_winrate(tmp_path):
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    cid = s.start_cycle()
    sid = s.save_signal(cycle_id=cid, pair="BTC/USDT", timeframe="15m",
                        signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True)
    s.save_outcome(signal_id=sid, horizon="4h", measured_at=t,
                   price_then=105.0, return_pct=5.0, verdict="correct")

    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 1" in text
    assert "BUY" in text
    assert "4h: 100% (1/1)" in text


def test_report_handles_empty(tmp_path):
    t = datetime(2026, 5, 17, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    text = build_report(storage=s, since=t, until=t)
    assert "Señales: 0" in text


def test_hodl_return_equal_weight():
    base = pd.Timestamp("2026-05-17", tz="UTC")
    df = pd.DataFrame([
        {"timestamp": base, "open": 0, "high": 0, "low": 0, "close": 100, "volume": 1},
        {"timestamp": base + pd.Timedelta(hours=1), "open": 0, "high": 0, "low": 0, "close": 110, "volume": 1},
    ])
    assert round(hodl_return_pct({"BTC/USDT": df}), 2) == 10.0


def test_max_drawdown():
    equity = [1000, 1100, 900, 950]
    assert round(max_drawdown_pct(equity), 2) == -18.18


def test_winrate_excludes_neutral_holds(tmp_path):
    """A HOLD with a neutral outcome must NOT dilute the win-rate; it should
    count only actionable (correct/incorrect) outcomes."""
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    cid = s.start_cycle()
    sid1 = s.save_signal(cycle_id=cid, pair="BTC/USDT", timeframe="15m",
                         signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True)
    s.save_outcome(signal_id=sid1, horizon="4h", measured_at=t,
                   price_then=105.0, return_pct=5.0, verdict="correct")
    sid2 = s.save_signal(cycle_id=cid, pair="ETH/USDT", timeframe="15m",
                         signal=_sig(SignalAction.HOLD), price_at_signal=100.0, delivered=False)
    s.save_outcome(signal_id=sid2, horizon="4h", measured_at=t,
                   price_then=100.1, return_pct=0.1, verdict="neutral")
    text = build_report(storage=s, since=t, until=t)
    # Only the actionable BUY counts: 1/1, not 1/2.
    assert "4h: 100% (1/1)" in text


def test_report_shows_drawdown_and_per_pair(tmp_path):
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    s.save_wallet(cash=900.0, vault=0.0, bankruptcies=0)
    # Two trades: +100 then -200 -> realized equity 1000, 1100, 900 -> dd -18.18%
    s.save_trade(pair="BTC/USDT", qty=1.0, entry_price=100.0, exit_price=200.0,
                 gross_profit=100.0, fees=0.0, net_profit=100.0, to_vault=0.0,
                 opened_at=t, closed_at=t)
    s.save_trade(pair="ETH/USDT", qty=1.0, entry_price=200.0, exit_price=0.0,
                 gross_profit=-200.0, fees=0.0, net_profit=-200.0, to_vault=0.0,
                 opened_at=t, closed_at=t + timedelta(hours=1))
    text = build_report(storage=s, since=t, until=t, initial_cash=1000.0)
    assert "Max drawdown (realizado): -18.18%" in text
    assert "BTC/USDT: P&L +100.00€ (1 trades)" in text
    assert "ETH/USDT: P&L -200.00€ (1 trades)" in text


def test_report_per_pair_signals(tmp_path):
    t = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    s = Storage(db_path=tmp_path / "bt.db")
    cid = s.start_cycle()
    s.save_signal(cycle_id=cid, pair="BTC/USDT", timeframe="15m",
                  signal=_sig(SignalAction.BUY), price_at_signal=100.0, delivered=True)
    s.save_signal(cycle_id=cid, pair="ETH/USDT", timeframe="15m",
                  signal=_sig(SignalAction.HOLD), price_at_signal=100.0, delivered=False)
    text = build_report(storage=s, since=t, until=t)
    assert "## Señales por par" in text
    assert "BTC/USDT" in text
    assert "ETH/USDT" in text
