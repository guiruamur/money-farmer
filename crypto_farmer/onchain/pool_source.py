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

    def _swap_price(self, data_hex: str) -> float:
        h = data_hex[2:] if data_hex.startswith("0x") else data_hex
        # word index 2 = sqrtPriceX96 -> chars [128:192]
        sqrt_price_x96 = int(h[128:192], 16)
        return price_from_sqrt(sqrt_price_x96, self._d0, self._d1)

    def _swap_volume(self, data_hex: str) -> float:
        h = data_hex[2:] if data_hex.startswith("0x") else data_hex
        # word 0 = amount0 (int256, two's complement) -> magnitude in token0 units
        raw = int(h[0:64], 16)
        if raw >= 2**255:
            raw -= 2**256
        return abs(raw) / (10 ** self._d0)

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int):
        from datetime import timedelta

        current = self._rpc.block_number()
        # Estimate the block range covering lookback*15m of history.
        span_seconds = lookback * 15 * 60
        span_blocks = int(span_seconds / self._block_time)
        from_block = max(0, current - span_blocks)
        logs = self._rpc.get_logs(
            address=self._pool, topics=[_SWAP_TOPIC0],
            from_block=from_block, to_block=current,
        )
        now = datetime.now(timezone.utc)
        rows = []
        for lg in logs:
            block = int(lg["blockNumber"], 16)
            # Approximate timestamp from block distance (no per-block RPC call).
            ts = now - timedelta(seconds=(current - block) * self._block_time)
            rows.append({
                "timestamp": pd.Timestamp(ts).floor("15min"),
                "price": self._swap_price(lg["data"]),
                "vol": self._swap_volume(lg["data"]),
            })
        if not rows:
            return pd.DataFrame(columns=_COLS)
        df = pd.DataFrame(rows).sort_values("timestamp")
        agg = df.groupby("timestamp").agg(
            open=("price", "first"), high=("price", "max"),
            low=("price", "min"), close=("price", "last"), volume=("vol", "sum"),
        ).reset_index()
        return agg[_COLS].tail(lookback).reset_index(drop=True)
