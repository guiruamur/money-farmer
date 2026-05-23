from crypto_farmer.cycle import CycleDeps


def test_cycledeps_accepts_clock():
    assert "clock" in CycleDeps.__dataclass_fields__
