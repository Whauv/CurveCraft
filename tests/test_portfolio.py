"""Phase 6 portfolio tests."""

from __future__ import annotations

from datetime import date

import pytest

from fixed_income.analytics.dv01 import dv01_from_curve
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument
from fixed_income.portfolio.portfolio import Portfolio

SETTLEMENT_DATE = date(2025, 1, 1)


def sample_curve():
    """Return a representative zero curve for portfolio tests."""
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


def test_portfolio_dv01_additive() -> None:
    """Portfolio DV01 should equal the sum of signed position DV01 values."""
    zero_curve = sample_curve()
    bond_one = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    bond_two = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.04,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2029, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    portfolio = Portfolio()
    portfolio.add_position(bond=bond_one, notional=2_000_000.0, direction=1)
    portfolio.add_position(bond=bond_two, notional=1_000_000.0, direction=-1)

    expected = (
        dv01_from_curve(bond=bond_one, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) * 2000.0
        - dv01_from_curve(bond=bond_two, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) * 1000.0
    )

    assert portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) == pytest.approx(
        expected,
        rel=1e-12,
    )


def test_hedge_neutralizes_dv01() -> None:
    """Applying the computed hedge trade should neutralize portfolio DV01."""
    zero_curve = sample_curve()
    core_bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    hedge_bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    portfolio = Portfolio()
    portfolio.add_position(bond=core_bond, notional=1_500_000.0, direction=1)

    hedge_notional = portfolio.hedge_trade(
        target_dv01=0.0,
        hedge_bond=hedge_bond,
        zero_curve=zero_curve,
        settlement_date=SETTLEMENT_DATE,
    )
    hedge_direction = 1 if hedge_notional >= 0.0 else -1
    portfolio.add_position(bond=hedge_bond, notional=abs(hedge_notional), direction=hedge_direction)

    assert portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE) == pytest.approx(
        0.0,
        abs=1e-8,
    )
