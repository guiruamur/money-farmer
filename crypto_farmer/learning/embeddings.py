from __future__ import annotations

from typing import Protocol

import httpx


class EmbeddingError(Exception):
    pass


class Embeddings(Protocol):
    def embed(self, text: str) -> list[float]: ...


class OllamaEmbeddings:
    def __init__(
        self, *, base_url: str, model: str,
        http_client: httpx.Client | None = None, timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._client = http_client or httpx.Client(timeout=timeout)

    def embed(self, text: str) -> list[float]:
        try:
            r = self._client.post(
                f"{self._base}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise EmbeddingError(f"ollama embeddings: {e}") from e
        data = r.json()
        return list(data["embedding"])
