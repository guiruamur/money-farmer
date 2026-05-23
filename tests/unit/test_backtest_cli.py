from datetime import datetime

from crypto_farmer.__main__ import _parse_backtest_args


def test_parse_backtest_args():
    ns = _parse_backtest_args(["--from", "2026-05-17", "--to", "2026-05-22",
                               "--pairs", "BTC/USDT,ETH/USDT"])
    assert ns.date_from == datetime(2026, 5, 17)
    assert ns.date_to == datetime(2026, 5, 22)
    assert ns.pairs == ["BTC/USDT", "ETH/USDT"]
