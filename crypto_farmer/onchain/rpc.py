from __future__ import annotations

from typing import Any

import httpx


class RpcError(Exception):
    pass


class RpcClient:
    """Minimal JSON-RPC 2.0 client over HTTP for reading the chain."""

    def __init__(self, *, url: str, timeout: float = 15.0,
                 http_client: httpx.Client | None = None) -> None:
        self._url = url
        self._client = http_client or httpx.Client(timeout=timeout)
        self._id = 0

    def _rpc(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        try:
            r = self._client.post(self._url, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Redact: the URL carries the API key in its path — never leak it
            # into error messages or tracebacks (use `from None`).
            raise RpcError(f"{method}: HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            raise RpcError(f"{method}: {type(e).__name__}") from None
        body = r.json()
        if "error" in body:
            raise RpcError(f"{method}: {body['error']}")
        return body["result"]

    def block_number(self) -> int:
        return int(self._rpc("eth_blockNumber", []), 16)

    def call(self, *, to: str, data: str) -> str:
        return self._rpc("eth_call", [{"to": to, "data": data}, "latest"])

    def get_logs(self, *, address: str, topics: list[str],
                 from_block: int, to_block: int) -> list[dict]:
        return self._rpc("eth_getLogs", [{
            "address": address,
            "topics": topics,
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        }])
