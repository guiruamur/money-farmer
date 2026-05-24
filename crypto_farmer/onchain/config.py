from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OnchainConfig:
    chain: str
    pool_address: str
    token0_decimals: int
    token1_decimals: int
    pair_label: str
    block_time_seconds: float
    rpc_url: str

    @classmethod
    def from_dict(cls, d: dict, *, rpc_url: str) -> "OnchainConfig":
        return cls(
            chain=d["chain"],
            pool_address=d["pool_address"],
            token0_decimals=int(d["token0_decimals"]),
            token1_decimals=int(d["token1_decimals"]),
            pair_label=d["pair_label"],
            block_time_seconds=float(d["block_time_seconds"]),
            rpc_url=rpc_url,
        )
