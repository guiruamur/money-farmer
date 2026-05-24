from crypto_farmer.onchain.pool_source import UniswapPoolSource


class _FakeRpc:
    def __init__(self, slot0_hex): self._slot0 = slot0_hex
    def call(self, *, to, data): return self._slot0
    def block_number(self): return 100
    def get_logs(self, **k): return []


def _slot0_hex(sqrt_price_x96: int) -> str:
    word = sqrt_price_x96.to_bytes(32, "big").hex()
    return "0x" + word + "00" * 32 + "00" * 32


def test_fetch_ticker_price():
    sqrt = int(5.4772e-5 * (2**96))  # ~3000 for WETH/USDC
    src = UniswapPoolSource(
        rpc=_FakeRpc(_slot0_hex(sqrt)), pool_address="0xpool",
        decimals0=18, decimals1=6, pair_label="ETH/USDC", block_time_seconds=2,
    )
    t = src.fetch_ticker("ETH/USDC")
    assert t.pair == "ETH/USDC"
    assert 2900 < t.price < 3100
