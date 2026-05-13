"""Virtual paper trader.

Reglas (Fase 2):
- Inicio: cash = initial_cash, vault = 0, positions = {}.
- Solo posiciones largas (long-only). No piramidamos: si ya hay posición del par,
  una nueva BUY se ignora.
- BUY: invierte position_size_pct del cash actual en el par. Se aplica fee_rate
  sobre el notional (cost = notional + fee). Si cash < cost mínimo razonable
  (notional > 0), la señal se ignora.
- SELL con posición abierta: cierra entera al precio actual. Se aplica fee_rate
  sobre el notional de salida. Si net_profit > 0 → vault recibe vault_pct del
  net_profit, el resto vuelve al cash. Si net_profit <= 0 → todo vuelve al cash.
- SELL sin posición: ignorada con detalle.
- HOLD: ignorada.
- Bancarrota: tras cerrar un trade con pérdida, si cash <= 0 y no quedan
  posiciones abiertas, se declara bancarrota: cash <- initial_cash, vault se
  mantiene, bankruptcies += 1.

El trader es síncrono y no entiende de tiempo más allá de los timestamps
auto-aplicados al persistir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from crypto_farmer.logging_setup import get_logger
from crypto_farmer.paper.models import (
    ActionKind, ActionOutcome, Position, TradeResult, WalletState,
)
from crypto_farmer.signals.models import SignalAction
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


@dataclass
class PaperTraderConfig:
    initial_cash: float
    position_size_pct: float  # 0..1; e.g. 0.20 = 20%
    vault_pct: float          # 0..1; e.g. 0.20 = 20% del profit a la caja fuerte
    fee_rate: float           # 0..1; e.g. 0.001 = 0.1%

    def validate(self) -> None:
        if not (0 < self.position_size_pct <= 1):
            raise ValueError("position_size_pct must be in (0, 1]")
        if not (0 <= self.vault_pct <= 1):
            raise ValueError("vault_pct must be in [0, 1]")
        if not (0 <= self.fee_rate < 0.5):
            raise ValueError("fee_rate must be in [0, 0.5)")
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be > 0")


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class PaperTrader:
    def __init__(self, *, storage: Storage, config: PaperTraderConfig) -> None:
        config.validate()
        self._storage = storage
        self._cfg = config
        # Lazy-init wallet on first use (or first construction)
        if self._storage.get_wallet() is None:
            self._storage.save_wallet(
                cash=config.initial_cash, vault=0.0, bankruptcies=0
            )

    # ----- public -----

    def wallet(self) -> WalletState:
        row = self._storage.get_wallet()
        assert row is not None  # init guarantees this
        return WalletState(
            cash=float(row["cash"]),
            vault=float(row["vault"]),
            bankruptcies=int(row["bankruptcies"]),
        )

    def positions(self) -> list[Position]:
        rows = self._storage.list_positions()
        return [
            Position(
                pair=r["pair"], qty=float(r["qty"]),
                avg_entry_price=float(r["avg_entry_price"]),
                opened_at=_parse_iso(r["opened_at"]),
                id=int(r["id"]),
            )
            for r in rows
        ]

    def on_signal(
        self, *, pair: str, action: SignalAction, price: float,
        now: datetime | None = None,
    ) -> ActionOutcome:
        """Process a signal and update wallet/positions."""
        now = now or datetime.now(timezone.utc)
        if action == SignalAction.HOLD:
            return ActionOutcome(kind=ActionKind.IGNORED_HOLD, pair=pair)
        if action == SignalAction.BUY:
            return self._handle_buy(pair=pair, price=price, now=now)
        if action == SignalAction.SELL:
            return self._handle_sell(pair=pair, price=price, now=now)
        # Defensive: unknown action type
        return ActionOutcome(
            kind=ActionKind.IGNORED_HOLD, pair=pair, detail=f"unknown_action:{action}"
        )

    # ----- private -----

    def _handle_buy(self, *, pair: str, price: float, now: datetime) -> ActionOutcome:
        existing = self._storage.get_position(pair=pair)
        if existing is not None:
            return ActionOutcome(
                kind=ActionKind.IGNORED_HAS_POS, pair=pair,
                detail="ya hay posición abierta (no se piramida)",
            )
        wallet = self.wallet()
        notional = wallet.cash * self._cfg.position_size_pct
        if notional <= 0:
            return ActionOutcome(
                kind=ActionKind.IGNORED_NO_CASH, pair=pair, detail="cash agotado",
            )
        fee = notional * self._cfg.fee_rate
        cost = notional + fee
        if cost > wallet.cash:
            # No debería pasar dado el sizing, pero por seguridad
            return ActionOutcome(
                kind=ActionKind.IGNORED_NO_CASH, pair=pair,
                detail=f"cost {cost:.2f} > cash {wallet.cash:.2f}",
            )
        qty = notional / price
        new_cash = wallet.cash - cost
        self._storage.save_wallet(
            cash=new_cash, vault=wallet.vault, bankruptcies=wallet.bankruptcies,
        )
        pos_id = self._storage.upsert_position(
            pair=pair, qty=qty, avg_entry_price=price, opened_at=now,
        )
        log.info("paper_open", extra={
            "pair": pair, "qty": qty, "entry": price, "fee": fee, "cash_after": new_cash,
        })
        return ActionOutcome(
            kind=ActionKind.OPENED, pair=pair,
            position=Position(
                pair=pair, qty=qty, avg_entry_price=price, opened_at=now, id=pos_id,
            ),
        )

    def _handle_sell(self, *, pair: str, price: float, now: datetime) -> ActionOutcome:
        row = self._storage.get_position(pair=pair)
        if row is None:
            return ActionOutcome(
                kind=ActionKind.IGNORED_NO_POS, pair=pair,
                detail="señal SELL pero no hay posición de este par",
            )

        qty = float(row["qty"])
        entry_price = float(row["avg_entry_price"])
        opened_at = _parse_iso(row["opened_at"])

        notional_in = qty * entry_price
        notional_out = qty * price
        # Fees: la entrada ya se descontó cuando abrimos. Ahora cobramos fee de salida.
        fee_out = notional_out * self._cfg.fee_rate
        # Sin embargo, conviene atribuir ambas fees al trade para análisis P&L.
        fee_in = notional_in * self._cfg.fee_rate
        gross_profit = notional_out - notional_in
        net_profit = gross_profit - fee_out  # la fee_in ya está fuera del cash actual

        # Para repartir entre cash y vault: lo que recibimos del cierre = notional_out - fee_out
        proceeds = notional_out - fee_out

        to_vault = 0.0
        if net_profit > 0:
            to_vault = net_profit * self._cfg.vault_pct
            proceeds -= to_vault  # se desvía al vault, no vuelve al cash

        wallet = self.wallet()
        new_cash = wallet.cash + proceeds
        new_vault = wallet.vault + to_vault
        self._storage.save_wallet(
            cash=new_cash, vault=new_vault, bankruptcies=wallet.bankruptcies,
        )
        self._storage.delete_position(pair=pair)
        trade_id = self._storage.save_trade(
            pair=pair, qty=qty, entry_price=entry_price, exit_price=price,
            gross_profit=gross_profit, fees=fee_in + fee_out, net_profit=net_profit,
            to_vault=to_vault, opened_at=opened_at, closed_at=now,
        )
        trade = TradeResult(
            pair=pair, qty=qty, entry_price=entry_price, exit_price=price,
            gross_profit=gross_profit, fees=fee_in + fee_out, net_profit=net_profit,
            to_vault=to_vault, opened_at=opened_at, closed_at=now, id=trade_id,
        )
        log.info("paper_close", extra={
            "pair": pair, "qty": qty, "exit": price, "net_profit": net_profit,
            "to_vault": to_vault, "cash_after": new_cash,
        })

        bankrupt = False
        # Bancarrota: tras este cierre, si no quedan posiciones abiertas y el cash
        # restante es menor que 1€ (por debajo de eso no se puede operar de forma útil).
        if new_cash < 1.0 and not self._storage.list_positions():
            self._storage.save_wallet(
                cash=self._cfg.initial_cash,
                vault=new_vault,
                bankruptcies=wallet.bankruptcies + 1,
            )
            log.warning("paper_bankruptcy", extra={
                "bankruptcies_after": wallet.bankruptcies + 1,
                "vault_preserved": new_vault,
            })
            bankrupt = True

        return ActionOutcome(
            kind=ActionKind.CLOSED, pair=pair, trade=trade, bankruptcy=bankrupt,
        )
