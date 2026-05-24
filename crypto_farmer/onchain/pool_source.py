from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from crypto_farmer.onchain.price_math import price_from_sqrt
from crypto_farmer.onchain.rpc import RpcClient
from crypto_farmer.signals.models import Ticker

_SLOT0_SELECTOR = "0x3850c7bd"
_SWAP_TOPIC0 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


class UniswapPoolSource:
    """MarketDataSource backed by a Uniswap v3 pool read over RPC."""

    def __init__(self, *, rpc: RpcClient, pool_address: str,
                 decimals0: int, decimals1: int, pair_label: str,
                 block_time_seconds: float) -> None:
        self._rpc = rpc
        self._pool = pool_address
        self._d0 = decimals0
        self._d1 = decimals1
        self._pair = pair_label
        self._block_time = block_time_seconds

    def _current_price(self) -> float:
        raw = self._rpc.call(to=self._pool, data=_SLOT0_SELECTOR)
        h = raw[2:] if raw.startswith("0x") else raw
        sqrt_price_x96 = int(h[0:64], 16)  # first 32-byte word
        return price_from_sqrt(sqrt_price_x96, self._d0, self._d1)

    def fetch_ticker(self, pair: str) -> Ticker:
        return Ticker(pair=self._pair, price=self._current_price(),
                      timestamp=datetime.now(timezone.utc))
