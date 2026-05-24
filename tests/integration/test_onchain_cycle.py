from crypto_farmer.onchain.runner import build_onchain_cycle
from crypto_farmer.onchain.config import OnchainConfig
from crypto_farmer.onchain.pool_source import UniswapPoolSource


def _swap_log(block, sqrt, amount0):
    def w(v): return (v % (2**256)).to_bytes(32, "big").hex()
    return {"data": "0x" + w(amount0) + w(0) + w(sqrt) + w(0) + w(0), "blockNumber": hex(block)}


class _FakeRpc:
    def __init__(self):
        sqrt = int(5.4772e-5 * (2**96))
        # swaps spread across blocks so they fall into many distinct 15m buckets
        self._logs = [_swap_log(1000 + i * 500, int(sqrt * (1 + i * 0.002)), 10**18) for i in range(80)]
    def block_number(self): return 1000 + 79 * 500
    def call(self, *, to, data): return "0x" + "00" * 96
    def get_logs(self, *, address, topics, from_block, to_block):
        return [l for l in self._logs if from_block <= int(l["blockNumber"], 16) <= to_block]


class _FakeEmbeddings:
    def embed(self, text): return [0.0, 0.0, 0.0]


class _AlwaysHoldLLM:
    def analyze(self, context):
        from crypto_farmer.llm.client import RawLLMResponse
        return RawLLMResponse(text='{"action":"HOLD","confidence":50,"reasoning":"r",'
                                   '"entry_price_hint":null,"invalidation_level":null,'
                                   '"time_horizon":"short","key_factors":[]}')


def test_onchain_cycle_runs_isolated(tmp_path):
    cfg = OnchainConfig(chain="base", pool_address="0xpool", token0_decimals=18,
                        token1_decimals=6, pair_label="ETH/USDC",
                        block_time_seconds=2, rpc_url="x")
    source = UniswapPoolSource(
        rpc=_FakeRpc(), pool_address=cfg.pool_address,
        decimals0=cfg.token0_decimals, decimals1=cfg.token1_decimals,
        pair_label=cfg.pair_label, block_time_seconds=cfg.block_time_seconds,
    )
    cycle = build_onchain_cycle(
        onchain_cfg=cfg, data_dir=tmp_path / "onchain", market=source,
        llm_client=_AlwaysHoldLLM(), embeddings=_FakeEmbeddings(),
    )
    result = cycle.run()
    assert result.status.value in ("ok", "degraded")
