"""Phase 4 analytics tests."""

from __future__ import annotations

from datetime import date

import pytest

from fixed_income.analytics.convexity import convexity, effective_convexity
from fixed_income.analytics.duration import effective_duration, macaulay_duration, modified_duration
from fixed_income.analytics.dv01 import dv01, dv01_from_curve
from fixed_income.analytics.key_rate_dv01 import STANDARD_TENOR_BUCKETS, key_rate_dv01
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument

FACE_VALUE = 1000.0
SETTLEMENT_DATE = date(2025, 1, 1)


def sample_curve():
    """Return a representative zero curve for effective-risk tests."""
    instruments = [
        MarketInstrument(instrument_type="deposit", tenor="1M", rate=0.0500, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="3M", rate=0.0510, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="6M", rate=0.0515, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="1Y", rate=0.0520, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="2Y", rate=0.0525, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="5Y", rate=0.0530, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="10Y", rate=0.0535, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="30Y", rate=0.0540, settlement_days=2),
    ]
    return Bootstrapper(instruments).bootstrap()


def test_modified_duration_formula() -> None:
    """Known 10Y bond duration values should be reproduced under the engine conventions."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    yield_ = 0.06

    macaulay = macaulay_duration(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)
    modified = modified_duration(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)

    assert macaulay == pytest.approx(7.6616410710, abs=1e-6)
    assert modified == pytest.approx(7.4384864767, abs=1e-6)


def test_dv01_price_sensitivity() -> None:
    """Dirty price sensitivity to a 1bp move should match DV01."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    yield_ = 0.06

    base_price = bond.dirty_price(yield_=yield_, settlement_date=SETTLEMENT_DATE)
    price_up = bond.dirty_price(yield_=yield_ + 1e-4, settlement_date=SETTLEMENT_DATE)
    price_change = price_up - base_price

    assert price_change == pytest.approx(-dv01(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE), rel=1e-3)


def test_convexity_positive() -> None:
    """Option-free bond convexity should be positive."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )

    assert convexity(bond=bond, yield_=0.06, settlement_date=SETTLEMENT_DATE) > 0.0


def test_effective_risk_measures_positive() -> None:
    """Curve-based effective duration, convexity, and DV01 should be positive."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    zero_curve = sample_curve()

    assert effective_duration(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) > 0.0
    assert effective_convexity(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) > 0.0
    assert dv01_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) > 0.0


def test_key_rate_sum() -> None:
    """Sum of key-rate DV01s should approximate total curve DV01."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    zero_curve = sample_curve()

    key_rate_map, key_rate_series = key_rate_dv01(
        bond=bond,
        zero_curve=zero_curve,
        settlement_date=SETTLEMENT_DATE,
    )
    total_curve_dv01 = dv01_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)

    assert list(key_rate_series.index) == STANDARD_TENOR_BUCKETS
    assert set(key_rate_map) == set(STANDARD_TENOR_BUCKETS)
    assert key_rate_series.sum() == pytest.approx(total_curve_dv01, rel=0.05)
