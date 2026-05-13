from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_farmer.paper.models import ActionKind
from crypto_farmer.paper.trader import PaperTrader, PaperTraderConfig
from crypto_farmer.signals.models import SignalAction
from crypto_farmer.storage.db import Storage


def _trader(tmp_path: Path, **overrides) -> PaperTrader:
    cfg = PaperTraderConfig(
        initial_cash=overrides.get("initial_cash", 1000.0),
        position_size_pct=overrides.get("position_size_pct", 0.20),
        vault_pct=overrides.get("vault_pct", 0.20),
        fee_rate=overrides.get("fee_rate", 0.001),
    )
    storage = Storage(db_path=tmp_path / "t.db")
    return PaperTrader(storage=storage, config=cfg)


def test_initial_wallet_is_seeded(tmp_path: Path):
    t = _trader(tmp_path)
    w = t.wallet()
    assert w.cash == 1000.0
    assert w.vault == 0.0
    assert w.bankruptcies == 0


def test_buy_opens_position_and_deducts_cash(tmp_path: Path):
    t = _trader(tmp_path)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    assert out.kind == ActionKind.OPENED
    pos = out.position
    assert pos is not None
    # 1000 * 0.20 = 200 notional, qty = 200 / 100 = 2, fee = 200 * 0.001 = 0.2
    assert pos.qty == pytest.approx(2.0)
    w = t.wallet()
    # cash = 1000 - 200 (notional) - 0.2 (fee) = 799.8
    assert w.cash == pytest.approx(799.8)


def test_buy_ignored_when_already_open(tmp_path: Path):
    t = _trader(tmp_path)
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=110.0)
    assert out.kind == ActionKind.IGNORED_HAS_POS
    assert len(t.positions()) == 1


def test_sell_without_position_is_ignored(tmp_path: Path):
    t = _trader(tmp_path)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.SELL, price=100.0)
    assert out.kind == ActionKind.IGNORED_NO_POS
    assert t.wallet().cash == 1000.0


def test_sell_close_with_profit_moves_to_vault(tmp_path: Path):
    t = _trader(tmp_path, vault_pct=0.20, fee_rate=0.0)  # no fees for math simplicity
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    # qty = 200/100 = 2, cash = 800
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.SELL, price=150.0)
    assert out.kind == ActionKind.CLOSED
    trade = out.trade
    assert trade is not None
    # gross_profit = 2 * 150 - 2 * 100 = 100. fees=0. net=100. to_vault=20.
    assert trade.net_profit == pytest.approx(100.0)
    assert trade.to_vault == pytest.approx(20.0)
    w = t.wallet()
    # cash: 800 (after buy) + (300 proceeds - 0 fee - 20 vault) = 800 + 280 = 1080
    assert w.cash == pytest.approx(1080.0)
    assert w.vault == pytest.approx(20.0)
    assert out.bankruptcy is False


def test_sell_close_with_loss_no_vault(tmp_path: Path):
    t = _trader(tmp_path, fee_rate=0.0)
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.SELL, price=50.0)
    trade = out.trade
    assert trade is not None
    assert trade.net_profit < 0
    assert trade.to_vault == 0.0
    w = t.wallet()
    # cash: 800 + (100 proceeds) = 900, vault still 0
    assert w.cash == pytest.approx(900.0)
    assert w.vault == pytest.approx(0.0)


def test_bankruptcy_when_total_loss(tmp_path: Path):
    # Buy 100% of cash (sizing=1.0), close at very low price -> cash = 0 -> bankruptcy
    t = _trader(tmp_path, position_size_pct=1.0, fee_rate=0.0)
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    # qty = 1000/100 = 10, cash = 0 (all in)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.SELL, price=0.01)
    assert out.kind == ActionKind.CLOSED
    assert out.bankruptcy is True
    w = t.wallet()
    # cash reset to initial, vault still 0, bankruptcies = 1
    assert w.cash == 1000.0
    assert w.bankruptcies == 1
    assert w.vault == 0.0


def test_bankruptcy_preserves_vault(tmp_path: Path):
    t = _trader(tmp_path, position_size_pct=1.0, fee_rate=0.0)
    # Primero un trade ganador para llenar el vault
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    t.on_signal(pair="BTC/USDT", action=SignalAction.SELL, price=200.0)
    w_after_win = t.wallet()
    assert w_after_win.vault > 0  # sanity
    vault_saved = w_after_win.vault

    # Ahora un trade catastrófico (with 100% of remaining cash)
    t.on_signal(pair="ETH/USDT", action=SignalAction.BUY, price=2000.0)
    out = t.on_signal(pair="ETH/USDT", action=SignalAction.SELL, price=0.01)
    assert out.bankruptcy is True
    w = t.wallet()
    assert w.cash == 1000.0
    assert w.bankruptcies == 1
    assert w.vault == pytest.approx(vault_saved)  # vault preservado


def test_hold_signal_is_silent(tmp_path: Path):
    t = _trader(tmp_path)
    out = t.on_signal(pair="BTC/USDT", action=SignalAction.HOLD, price=100.0)
    assert out.kind == ActionKind.IGNORED_HOLD
    # Estado intacto
    w = t.wallet()
    assert w.cash == 1000.0


def test_config_validates_ranges(tmp_path: Path):
    with pytest.raises(ValueError):
        PaperTraderConfig(
            initial_cash=1000, position_size_pct=1.5, vault_pct=0.2, fee_rate=0.001
        ).validate()
    with pytest.raises(ValueError):
        PaperTraderConfig(
            initial_cash=0, position_size_pct=0.2, vault_pct=0.2, fee_rate=0.001
        ).validate()


def test_multiple_pairs_open_simultaneously(tmp_path: Path):
    t = _trader(tmp_path, position_size_pct=0.20, fee_rate=0.0)
    t.on_signal(pair="BTC/USDT", action=SignalAction.BUY, price=100.0)
    t.on_signal(pair="ETH/USDT", action=SignalAction.BUY, price=2000.0)
    positions = t.positions()
    assert len(positions) == 2
    pairs = {p.pair for p in positions}
    assert pairs == {"BTC/USDT", "ETH/USDT"}
    # cash: 1000 - 200 (BTC) - 160 (20% of remaining 800 = 160 for ETH) = 640
    assert t.wallet().cash == pytest.approx(640.0)
