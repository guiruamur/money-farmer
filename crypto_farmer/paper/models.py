"""Paper trading domain models.

A WalletState is the singleton state of the virtual portfolio: cash available,
vault (untouchable savings), and a counter of bankruptcies.
A Position is a single open long position (no shorts in fase 2).
A TradeResult is the closed-trade record persisted to history for P&L analysis.
ActionOutcome describes what the PaperTrader did with a signal (executed, ignored, bankrupt).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass
class WalletState:
    cash: float
    vault: float
    bankruptcies: int

    def total(self, *, open_positions_value: float = 0.0) -> float:
        return self.cash + open_positions_value


@dataclass
class Position:
    pair: str
    qty: float
    avg_entry_price: float
    opened_at: datetime
    id: int | None = None  # filled by storage

    def value_at(self, current_price: float) -> float:
        return self.qty * current_price


@dataclass
class TradeResult:
    pair: str
    qty: float
    entry_price: float
    exit_price: float
    gross_profit: float
    fees: float
    net_profit: float
    to_vault: float
    opened_at: datetime
    closed_at: datetime
    id: int | None = None

    @property
    def return_pct(self) -> float:
        cost = self.qty * self.entry_price
        return (self.net_profit / cost * 100.0) if cost else 0.0


class ActionKind(str, Enum):
    OPENED = "opened"          # BUY ejecutada
    CLOSED = "closed"          # SELL ejecutada
    IGNORED_NO_POS = "ignored_no_position"  # SELL sin tener la cripto
    IGNORED_HAS_POS = "ignored_has_position"  # BUY teniendo ya la cripto (sin piramidar)
    IGNORED_NO_CASH = "ignored_no_cash"  # BUY sin cash suficiente
    IGNORED_HOLD = "ignored_hold"        # señal HOLD


@dataclass
class ActionOutcome:
    kind: ActionKind
    pair: str
    detail: str = ""
    trade: TradeResult | None = None
    position: Position | None = None
    bankruptcy: bool = False  # True si tras esta acción se declaró bancarrota
