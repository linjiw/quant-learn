from quant_learn.analytics.forward_analysis import _probability_gain


def test_probability_gain_increases_with_positive_drift() -> None:
    negative = _probability_gain(mu=-0.10, sigma=0.40, years=1.0)
    neutral = _probability_gain(mu=0.00, sigma=0.40, years=1.0)
    positive = _probability_gain(mu=0.10, sigma=0.40, years=1.0)

    assert negative < neutral < positive
    assert neutral == 0.5
