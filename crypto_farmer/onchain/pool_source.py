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
                 block_time_seconds: float, max_block_span: int = 10,
                 max_lookback_blocks: int = 100) -> None:
        self._rpc = rpc
        self._pool = pool_address
        self._d0 = decimals0
        self._d1 = decimals1
        self._pair = pair_label
        self._block_time = block_time_seconds
        # RPC providers cap eth_getLogs by block range. Alchemy's FREE tier
        # caps it at 10 blocks, so that is the default chunk size.
        self._max_block_span = max_block_span
        # And (W1-a) cap the total reconstructed range: with a 10-block limit,
        # rebuilding hours of history would need hundreds of calls. So W1-a
        # reads only a tiny recent window — fetch_ticker (slot0) is the real
        # price read; meaningful candle history needs another path (price
        # accumulation, an indexer, or a paid RPC tier). See W1 spec, section 12.
        self._max_lookback_blocks = max_lookback_blocks

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

    def _get_logs_paged(self, from_block: int, to_block: int) -> list[dict]:
        """Fetch Swap logs over [from_block, to_block] in chunks, since RPC
        providers cap eth_getLogs by result count / range."""
        logs: list[dict] = []
        b = from_block
        while b <= to_block:
            chunk_to = min(b + self._max_block_span - 1, to_block)
            logs.extend(self._rpc.get_logs(
                address=self._pool, topics=[_SWAP_TOPIC0],
                from_block=b, to_block=chunk_to,
            ))
            b = chunk_to + 1
        return logs

    def fetch_ohlcv(self, pair: str, timeframe: str, lookback: int):
        from datetime import timedelta

        current = self._rpc.block_number()
        # Estimate the block range covering lookback*15m of history.
        span_seconds = lookback * 15 * 60
        span_blocks = min(int(span_seconds / self._block_time), self._max_lookback_blocks)
        from_block = max(0, current - span_blocks)
        logs = self._get_logs_paged(from_block, current)
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
