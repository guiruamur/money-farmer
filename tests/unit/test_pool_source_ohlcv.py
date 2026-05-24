from crypto_farmer.onchain.pool_source import UniswapPoolSource


def _swap_log(block: int, sqrt_price_x96: int, amount0: int) -> dict:
    # data = amount0 (int256) | amount1 (int256) | sqrtPriceX96 (uint160) | liquidity | tick
    def w(v): return (v % (2**256)).to_bytes(32, "big").hex()
    data = "0x" + w(amount0) + w(0) + w(sqrt_price_x96) + w(0) + w(0)
    return {"data": data, "blockNumber": hex(block)}


class _FakeRpc:
    def __init__(self, logs, current_block): self._logs = logs; self._cb = current_block
    def block_number(self): return self._cb
    def call(self, *, to, data): return "0x" + "00" * 96
    def get_logs(self, *, address, topics, from_block, to_block):
        return [l for l in self._logs if from_block <= int(l["blockNumber"], 16) <= to_block]


def test_fetch_ohlcv_builds_candles():
    sqrt = int(5.4772e-5 * (2**96))  # ~3000
    logs = [_swap_log(1000, sqrt, 10**18), _swap_log(1001, int(sqrt * 1.01), 10**18)]
    src = UniswapPoolSource(
        rpc=_FakeRpc(logs, current_block=1001), pool_address="0xpool",
        decimals0=18, decimals1=6, pair_label="ETH/USDC", block_time_seconds=2,
    )
    df = src.fetch_ohlcv("ETH/USDC", "15m", lookback=100)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) >= 1
    assert 2900 < df["close"].iloc[-1] < 3200
    import pandas as pd
    assert df["timestamp"].max() <= pd.Timestamp.now(tz="UTC")


def test_fetch_ohlcv_empty_when_no_logs():
    src = UniswapPoolSource(
        rpc=_FakeRpc([], current_block=1001), pool_address="0xpool",
        decimals0=18, decimals1=6, pair_label="ETH/USDC", block_time_seconds=2,
    )
    df = src.fetch_ohlcv("ETH/USDC", "15m", lookback=100)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 0
