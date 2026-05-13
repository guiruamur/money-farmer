from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, *, by: int = 1) -> None:
        with self._lock:
            self._counters[name] += by

    def record_latency(self, name: str, value_ms: float) -> None:
        with self._lock:
            self._latencies[name].append(value_ms)

    def snapshot(self) -> dict:
        with self._lock:
            lat: dict[str, dict[str, float]] = {}
            for k, vals in self._latencies.items():
                if not vals:
                    continue
                lat[k] = {
                    "count": len(vals),
                    "avg_ms": sum(vals) / len(vals),
                    "max_ms": max(vals),
                }
            return deepcopy({
                "counters": dict(self._counters),
                "latencies": lat,
            })
