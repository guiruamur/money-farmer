from __future__ import annotations

from datetime import datetime

from crypto_farmer.storage.db import Storage


def build_report(*, storage: Storage, since: datetime, until: datetime) -> str:
    signals = storage.list_recent_signals(limit=100000)
    actions: dict[str, int] = {}
    for s in signals:
        actions[s["action"]] = actions.get(s["action"], 0) + 1

    wins = {"1h": 0, "4h": 0, "24h": 0}
    rated = {"1h": 0, "4h": 0, "24h": 0}
    for s in signals:
        for o in storage.list_outcomes_for_signal(s["id"]):
            h = o["horizon"]
            if h in rated:
                rated[h] += 1
                if o.get("verdict") == "correct":
                    wins[h] += 1

    def wr(h: str) -> str:
        return f"{round(100 * wins[h] / rated[h])}% ({wins[h]}/{rated[h]})" if rated[h] else "—"

    dist = ", ".join(f"{a}={n}" for a, n in actions.items()) or "—"
    lines = [
        f"# Backtest {since.date()} → {until.date()}",
        f"Señales: {len(signals)}. Distribución: {dist}",
        f"Win rate 1h: {wr('1h')}  ·  4h: {wr('4h')}  ·  24h: {wr('24h')}",
    ]

    wallet = storage.get_wallet()
    if wallet is not None:
        trades = storage.list_trades(limit=100000)
        total_pnl = sum(float(t["net_profit"]) for t in trades)
        wins_n = sum(1 for t in trades if float(t["net_profit"]) > 0)
        lines += [
            "",
            "## Paper trading",
            f"P&L: {total_pnl:+.2f}€  ·  Trades: {len(trades)} "
            f"(ganadores {wins_n}/{len(trades)})  ·  "
            f"Cash {float(wallet['cash']):.2f}€  ·  Vault {float(wallet['vault']):.2f}€  ·  "
            f"Bancarrotas {wallet['bankruptcies']}",
        ]
    return "\n".join(lines)
