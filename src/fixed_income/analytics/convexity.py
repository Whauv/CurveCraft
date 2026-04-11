"""Convexity analytics for fixed income instruments."""

from __future__ import annotations

from datetime import date

from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve
from fixed_income.utils.day_count import year_fraction

from .duration import BASIS_POINT, price_from_curve


def convexity(bond: Bond, yield_: float, settlement_date: date) -> float:
    """Compute yield-based convexity.

    Parameters
    ----------
    bond : Bond
        Bond to analyze.
    yield_ : float
        Annualized yield to maturity expressed as a decimal.
    settlement_date : date
        Valuation or settlement date.

    Returns
    -------
    float
        Convexity measure in years squared.
    """
    price = bond.dirty_price(yield_=yield_, settlement_date=settlement_date)
    if price <= 0.0:
        return 0.0

    convexity_numerator = 0.0
    future_cash_flows = bond.get_cash_flows()
    future_cash_flows = future_cash_flows[future_cash_flows["date"] > settlement_date]
    for row in future_cash_flows.itertuples(index=False):
        time_in_years = year_fraction(
            start_date=settlement_date,
            end_date=row.date,
            convention=bond.day_count_convention,
            frequency=bond.frequency,
        )
        period_count = bond.frequency * time_in_years
        discount_factor = (1.0 + yield_ / bond.frequency) ** period_count
        present_value = row.total_cf / discount_factor
        # Discrete convexity: [1 / (P * (1 + y/m)^2)] * sum((t_p * (t_p + 1) / m^2) * PV(CF_t))
        convexity_numerator += (period_count * (period_count + 1.0) / (bond.frequency**2)) * present_value
    return float(convexity_numerator / (price * (1.0 + yield_ / bond.frequency) ** 2))


def effective_convexity(
    bond: Bond,
    zero_curve: ZeroCurve,
    settlement_date: date,
    bump_bps: float = 1.0,
) -> float:
    """Compute effective convexity from full curve repricing.

    Parameters
    ----------
    bond : Bond
        Bond to analyze.
    zero_curve : ZeroCurve
        Base zero curve.
    settlement_date : date
        Valuation or settlement date.
    bump_bps : float, optional
        Parallel shift size in basis points.

    Returns
    -------
    float
        Effective convexity.
    """
    bump = bump_bps * BASIS_POINT
    base_price = price_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    if base_price <= 0.0:
        return 0.0
    down_curve = zero_curve.bumped_parallel(-bump)
    up_curve = zero_curve.bumped_parallel(bump)
    price_down = price_from_curve(bond=bond, zero_curve=down_curve, settlement_date=settlement_date)
    price_up = price_from_curve(bond=bond, zero_curve=up_curve, settlement_date=settlement_date)
    # Effective convexity: (P_up + P_down - 2 * P) / (P * bump^2)
    return float((price_up + price_down - 2.0 * base_price) / (base_price * bump**2))

