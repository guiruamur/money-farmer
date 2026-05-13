from __future__ import annotations

from crypto_farmer.storage.db import Storage


class FeedbackBuilder:
    def __init__(self, *, storage: Storage) -> None:
        self._storage = storage

    def build(self, *, lookback: int) -> dict:
        signals = self._storage.list_recent_signals(limit=lookback)
        if not signals:
            return {
                "lookback": lookback,
                "win_rate": 0,
                "summary": "Sin histórico previo.",
            }

        rated = []
        for s in signals:
            outcomes = self._storage.list_outcomes_for_signal(s["id"])
            verdict = None
            for h in ("4h", "1h", "24h"):
                match = next((o for o in outcomes if o["horizon"] == h), None)
                if match and match.get("verdict"):
                    verdict = match["verdict"]
                    break
            if verdict is not None:
                rated.append((s, verdict))

        if not rated:
            return {
                "lookback": lookback,
                "win_rate": 0,
                "summary": (
                    f"Hay {len(signals)} señales recientes pero ninguna tiene "
                    "outcome medido todavía."
                ),
            }

        correct = sum(1 for _, v in rated if v == "correct")
        wr = int(round(100 * correct / len(rated)))

        best = max(rated, key=lambda t: 1 if t[1] == "correct" else 0)
        worst = min(rated, key=lambda t: 1 if t[1] == "correct" else 0)
        summary_parts = [
            f"{len(rated)} señales medidas, {correct} correctas.",
            f"Última correcta: {best[0]['pair']} {best[0]['action']}.",
            f"Última incorrecta: {worst[0]['pair']} {worst[0]['action']}.",
        ]
        return {
            "lookback": lookback,
            "win_rate": wr,
            "summary": " ".join(summary_parts),
        }
