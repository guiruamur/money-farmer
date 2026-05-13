from __future__ import annotations

from dataclasses import dataclass

from crypto_farmer.learning.memory import MemoryHit


@dataclass
class _Entry:
    embedding: list[float]
    metadata: dict
    text: str


class InMemoryMemory:
    def __init__(self) -> None:
        self._entries: list[_Entry] = []

    def add(self, *, embedding, text, metadata) -> str:
        eid = str(len(self._entries))
        self._entries.append(_Entry(embedding=list(embedding), metadata={**metadata, "id": eid}, text=text))
        return eid

    def search(self, *, embedding, k, pair_filter=None) -> list[MemoryHit]:
        def cos(a, b):
            num = sum(x*y for x, y in zip(a, b))
            da = sum(x*x for x in a) ** 0.5
            db = sum(x*x for x in b) ** 0.5
            return num / (da*db) if da and db else 0.0

        ranked = []
        for e in self._entries:
            if pair_filter and e.metadata.get("pair") != pair_filter:
                continue
            ranked.append((cos(e.embedding, embedding), e))
        ranked.sort(key=lambda t: -t[0])
        return [
            MemoryHit(
                id=e.metadata["id"], score=s, text=e.text, metadata=e.metadata,
            )
            for s, e in ranked[:k]
        ]

    def update_outcome(
        self, *, entry_id: str, return_4h: float | None = None, return_24h: float | None = None
    ) -> None:
        for e in self._entries:
            if e.metadata.get("id") == entry_id:
                if return_4h is not None:
                    e.metadata["return_4h"] = return_4h
                if return_24h is not None:
                    e.metadata["return_24h"] = return_24h
                return
