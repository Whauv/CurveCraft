"""Phase 1 and Phase 2 bond tests."""

from __future__ import annotations

from datetime import date

import pytest

from fixed_income.bonds.bond import FixedRateBond
from fixed_income.bonds.zero_coupon import ZeroCouponBond

FACE_VALUE = 1000.0
PAR_COUPON = 0.04
SEMI_ANNUAL_FREQUENCY = 2
PAR_SETTLEMENT_DATE = date(2025, 1, 1)


def test_par_bond_price() -> None:
    """Coupon equal to yield should price at par on a coupon date."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=PAR_COUPON,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    assert bond.dirty_price(yield_=PAR_COUPON, settlement_date=PAR_SETTLEMENT_DATE) == pytest.approx(
        FACE_VALUE,
        abs=1e-10,
    )
    assert bond.clean_price(yield_=PAR_COUPON, settlement_date=PAR_SETTLEMENT_DATE) == pytest.approx(
        FACE_VALUE,
        abs=1e-10,
    )


def test_price_yield_inverse() -> None:
    """Higher yield should reduce price."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=PAR_COUPON,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    price_low_yield = bond.dirty_price(yield_=0.03, settlement_date=PAR_SETTLEMENT_DATE)
    price_par = bond.dirty_price(yield_=0.04, settlement_date=PAR_SETTLEMENT_DATE)
    price_high_yield = bond.dirty_price(yield_=0.05, settlement_date=PAR_SETTLEMENT_DATE)

    assert price_low_yield > price_par > price_high_yield


def test_accrued_interest_mid_period() -> None:
    """Accrued interest should scale with the elapsed fraction of the coupon period."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2027, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    settlement_date = date(2025, 4, 1)
    previous_coupon = date(2025, 1, 1)
    next_coupon = date(2025, 7, 1)
    expected = bond.coupon_amount * ((settlement_date - previous_coupon).days / (next_coupon - previous_coupon).days)

    assert bond.accrued_interest(settlement_date=settlement_date) == pytest.approx(expected, rel=1e-12)


def test_zero_coupon_price() -> None:
    """Zero coupon bond price should equal discounted face value."""
    bond = ZeroCouponBond(
        face_value=FACE_VALUE,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2027, 1, 1),
        day_count_convention="ACT/ACT",
    )

    yield_ = 0.05
    price = bond.dirty_price(yield_=yield_, settlement_date=date(2025, 1, 1))

    assert price == pytest.approx(FACE_VALUE / (1.05**2), rel=1e-12)


def test_ytm_roundtrip() -> None:
    """Pricing and YTM solving should round-trip within tolerance."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=0.045,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )
    settlement_date = date(2025, 1, 1)
    original_price = bond.dirty_price(yield_=0.0525, settlement_date=settlement_date)

    solved_ytm = bond.yield_to_maturity(dirty_price=original_price, settlement_date=settlement_date)
    repriced = bond.dirty_price(yield_=solved_ytm, settlement_date=settlement_date)

    assert repriced == pytest.approx(original_price, abs=1e-6)


def test_ytm_par_bond_equals_coupon_rate() -> None:
    """Par bond YTM should match the coupon rate."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=PAR_COUPON,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    ytm = bond.ytm(dirty_price=1000.0, settlement_date=PAR_SETTLEMENT_DATE)

    assert ytm == pytest.approx(PAR_COUPON, abs=1e-10)


def test_ytm_discount_bond_above_coupon_rate() -> None:
    """Discount bond YTM should exceed coupon rate."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=PAR_COUPON,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    ytm = bond.yield_to_maturity(dirty_price=950.0, settlement_date=PAR_SETTLEMENT_DATE)

    assert ytm > PAR_COUPON


def test_ytm_premium_bond_below_coupon_rate() -> None:
    """Premium bond YTM should be below coupon rate."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=PAR_COUPON,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=SEMI_ANNUAL_FREQUENCY,
        day_count_convention="ACT/ACT",
    )

    ytm = bond.yield_to_maturity(dirty_price=1050.0, settlement_date=PAR_SETTLEMENT_DATE)

    assert ytm < PAR_COUPON
