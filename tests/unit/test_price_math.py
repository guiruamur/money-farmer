from crypto_farmer.onchain.price_math import price_from_sqrt


def test_price_from_sqrt_equal_decimals():
    # sqrtPriceX96 = 2**96 -> ratio 1.0; equal decimals -> price 1.0
    assert abs(price_from_sqrt(2**96, 18, 18) - 1.0) < 1e-9


def test_price_from_sqrt_weth_usdc_realistic():
    # WETH/USDC v3 pool (token0=WETH 18 dec, token1=USDC 6 dec).
    # adjusted = (sqrt/2**96)**2 * 10**(18-6); pick sqrt for ~3000 USDC per WETH
    sqrt = int(5.4772e-5 * (2**96))
    price = price_from_sqrt(sqrt, 18, 6)
    assert 2900 < price < 3100
