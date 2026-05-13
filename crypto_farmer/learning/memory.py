from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MemoryHit:
    id: str
    score: float
    text: str
    metadata: dict[str, Any]


class Memory(Protocol):
    def add(self, *, embedding: list[float], text: str, metadata: dict) -> str: ...
    def search(
        self, *, embedding: list[float], k: int, pair_filter: str | None = None,
    ) -> list[MemoryHit]: ...
    def update_outcome(
        self, *, entry_id: str, return_4h: float, return_24h: float
    ) -> None: ...


class ChromaMemory:
    def __init__(self, *, persist_dir: str, collection_name: str) -> None:
        import chromadb
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"},
        )
        self._counter = self._collection.count()

    def add(self, *, embedding: list[float], text: str, metadata: dict) -> str:
        self._counter += 1
        entry_id = f"sit_{self._counter}"
        self._collection.add(
            ids=[entry_id], embeddings=[embedding],
            documents=[text], metadatas=[metadata],
        )
        return entry_id

    def search(
        self, *, embedding: list[float], k: int, pair_filter: str | None = None,
    ) -> list[MemoryHit]:
        where = {"pair": pair_filter} if pair_filter else None
        res = self._collection.query(
            query_embeddings=[embedding], n_results=k, where=where,
        )
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        hits: list[MemoryHit] = []
        for i, doc, meta, dist in zip(ids, docs, metas, dists):
            # cosine distance → score = 1 - dist
            hits.append(MemoryHit(id=i, score=max(0.0, 1.0 - float(dist)), text=doc, metadata=dict(meta)))
        return hits

    def update_outcome(
        self, *, entry_id: str, return_4h: float, return_24h: float
    ) -> None:
        existing = self._collection.get(ids=[entry_id])
        metas = existing.get("metadatas", [[]])
        if not metas or not metas[0]:
            return
        new_meta = dict(metas[0])
        new_meta["return_4h"] = return_4h
        new_meta["return_24h"] = return_24h
        self._collection.update(ids=[entry_id], metadatas=[new_meta])
