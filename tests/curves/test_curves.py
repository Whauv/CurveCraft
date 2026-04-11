"""Phase 3 curve tests."""

from __future__ import annotations

import numpy as np
import pytest

from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument


def sample_instruments() -> list[MarketInstrument]:
    """Return the Phase 3 sample deposit and swap quotes."""
    return [
        MarketInstrument(instrument_type="deposit", tenor="1M", rate=0.0500, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="3M", rate=0.0510, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="6M", rate=0.0515, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="1Y", rate=0.0520, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="2Y", rate=0.0525, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="5Y", rate=0.0530, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="10Y", rate=0.0535, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="30Y", rate=0.0540, settlement_days=2),
    ]


@pytest.fixture()
def zero_curve():
    """Build the sample zero curve."""
    bootstrapper = Bootstrapper(sample_instruments())
    return bootstrapper.bootstrap()


def test_df_starts_at_one(zero_curve) -> None:
    """Discount factor at time zero should be one."""
    assert zero_curve.discount_factor(0.0) == pytest.approx(1.0, abs=1e-12)


def test_df_monotone_decreasing(zero_curve) -> None:
    """Discount factors should decrease with maturity."""
    discount_factors = [zero_curve.discount_factor(t) for t in zero_curve.maturities]
    assert all(left > right for left, right in zip(discount_factors, discount_factors[1:]))


def test_forward_rates_positive(zero_curve) -> None:
    """Forward rates should stay positive across the curve."""
    maturities = np.linspace(0.25, 30.0, 120)
    forward_rates = [
        zero_curve.forward_rate(float(t1), float(t2))
        for t1, t2 in zip(maturities[:-1], maturities[1:])
    ]
    assert all(rate > 0.0 for rate in forward_rates)


def test_swap_reprices_to_par() -> None:
    """Bootstrapped curve should reprice input swaps to par."""
    repricing_curve = Bootstrapper(sample_instruments()).bootstrap(interpolation_method="log_linear")
    for instrument in sample_instruments():
        if instrument.instrument_type != "swap":
            continue
        maturity = instrument.maturity_in_years
        payment_times = np.arange(1.0, maturity + 1.0, 1.0)
        coupon_leg = instrument.rate * sum(repricing_curve.discount_factor(float(t)) for t in payment_times)
        swap_value = coupon_leg + repricing_curve.discount_factor(maturity)
        assert swap_value == pytest.approx(1.0, abs=1e-8)
