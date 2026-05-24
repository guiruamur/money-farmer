from __future__ import annotations


def price_from_sqrt(sqrt_price_x96: int, decimals0: int, decimals1: int) -> float:
    """Uniswap v3 sqrtPriceX96 -> price of token0 expressed in token1.

    price = (sqrtPriceX96 / 2**96)**2 gives token1/token0 in raw units;
    multiply by 10**(decimals0 - decimals1) to get human units.
    """
    ratio = (sqrt_price_x96 / (2**96)) ** 2
    return ratio * (10 ** (decimals0 - decimals1))
