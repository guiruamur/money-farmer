from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from crypto_farmer.storage.db import Storage


_SECRET_KEYS = {"bot_token", "cryptopanic_token", "api_key", "api_secret"}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("***" if k in _SECRET_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def format_status(cycles: list[dict], paused: bool) -> str:
    if not cycles:
        return "Sin ciclos ejecutados todavía. (0)"
    last = cycles[0]
    ok_count = sum(1 for c in cycles if c.get("status") == "ok")
    lines = [
        f"Estado: {'PAUSADO' if paused else 'ACTIVO'}",
        f"Último ciclo: #{last['id']} {last.get('status')} a las {last.get('finished_at')}",
        f"Ciclos OK en las últimas {len(cycles)} ejecuciones: {ok_count}",
    ]
    return "\n".join(lines)


def format_last_signals(signals: list[dict]) -> str:
    if not signals:
        return "Sin señales emitidas todavía."
    lines = ["Últimas señales:"]
    for s in signals:
        lines.append(
            f"- {s['pair']} {s['action']} conf {s['confidence']} ({s['generated_at']})"
        )
    return "\n".join(lines)


@dataclass
class CommandContext:
    storage: Storage
    scheduler_paused_getter: Callable[[], bool]
    scheduler_pauser: Callable[[], None]
    scheduler_resumer: Callable[[], None]
    health_checker: Callable[[], dict[str, str]]
    config_snapshot: dict


class BotCommands:
    def __init__(self, ctx: CommandContext) -> None:
        self._ctx = ctx

    def status(self) -> str:
        cycles = self._ctx.storage.list_recent_cycles(limit=24)
        return format_status(cycles, paused=self._ctx.scheduler_paused_getter())

    def last(self) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=5)
        return format_last_signals(sigs)

    def stats(self) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=100)
        if not sigs:
            return "Sin estadísticas: no hay señales todavía."
        actions: dict[str, int] = {}
        for s in sigs:
            actions[s["action"]] = actions.get(s["action"], 0) + 1
        wins = 0
        rated = 0
        for s in sigs:
            outcomes = self._ctx.storage.list_outcomes_for_signal(s["id"])
            verdict = next(
                (o["verdict"] for o in outcomes if o["horizon"] == "4h"), None
            )
            if verdict is not None:
                rated += 1
                if verdict == "correct":
                    wins += 1
        wr = int(round(100 * wins / rated)) if rated else 0
        lines = [
            f"Señales recientes: {len(sigs)}",
            "Distribución: " + ", ".join(f"{k}={v}" for k, v in actions.items()),
            f"Win rate (4h): {wr}% ({wins}/{rated} medidas)",
        ]
        return "\n".join(lines)

    def pair(self, pair: str) -> str:
        sigs = self._ctx.storage.list_recent_signals(limit=5, pair=pair)
        if not sigs:
            return f"Sin señales recientes para {pair}."
        lines = [f"Últimas señales para {pair}:"]
        for s in sigs:
            outcomes = self._ctx.storage.list_outcomes_for_signal(s["id"])
            outcomes_str = ", ".join(
                f"{o['horizon']}={o.get('return_pct', '?')}%" for o in outcomes
            ) or "(sin outcomes)"
            lines.append(
                f"- {s['action']} conf {s['confidence']} en {s['generated_at']} → {outcomes_str}"
            )
        return "\n".join(lines)

    def pause(self) -> str:
        self._ctx.scheduler_pauser()
        return "Scheduler en pausa. Usa /resume para reanudar."

    def resume(self) -> str:
        self._ctx.scheduler_resumer()
        return "Scheduler reanudado."

    def health(self) -> str:
        checks = self._ctx.health_checker()
        return "Health:\n" + "\n".join(f"- {k}: {v}" for k, v in checks.items())

    def config(self) -> str:
        redacted = _redact(self._ctx.config_snapshot)
        return "```\n" + json.dumps(redacted, indent=2, ensure_ascii=False) + "\n```"
