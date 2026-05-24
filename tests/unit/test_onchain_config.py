from crypto_farmer.onchain.config import OnchainConfig


def test_onchain_config_from_dict():
    cfg = OnchainConfig.from_dict({
        "chain": "base",
        "pool_address": "0xPOOL",
        "token0_decimals": 18,
        "token1_decimals": 6,
        "pair_label": "ETH/USDC",
        "block_time_seconds": 2,
    }, rpc_url="https://rpc")
    assert cfg.pool_address == "0xPOOL"
    assert cfg.token0_decimals == 18
    assert cfg.rpc_url == "https://rpc"
    assert cfg.pair_label == "ETH/USDC"
