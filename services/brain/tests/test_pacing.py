from app.pacing import remaining_micros, spend_micros_from_price


def test_spend_formula_multiplier_52():
    assert spend_micros_from_price(10.0, 5.2) == 52000


def test_remaining_never_below_zero():
    assert remaining_micros(100, 40, 20) == 40
    assert remaining_micros(100, 90, 20) == 0
    assert remaining_micros(50_000_000, 0, 0) == 50_000_000
