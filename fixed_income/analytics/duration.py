"""Duration analytics for fixed income instruments."""

from __future__ import annotations

from datetime import date

from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve
from fixed_income.utils.day_count import year_fraction

BASIS_POINT = 1e-4


def price_from_curve(bond: Bond, zero_curve: ZeroCurve, settlement_date: date) -> float:
    """Price a bond from a zero curve using discounted future cash flows.

    Parameters
    ----------
    bond : Bond
        Bond to be priced.
    zero_curve : ZeroCurve
        Zero curve used for discounting.
    settlement_date : date
        Valuation or settlement date.

    Returns
    -------
    float
        Dirty price from the zero curve.
    """
    future_cash_flows = bond.get_cash_flows()
    future_cash_flows = future_cash_flows[future_cash_flows["date"] > settlement_date]
    if future_cash_flows.empty:
        return 0.0

    price = 0.0
    for row in future_cash_flows.itertuples(index=False):
        time_in_years = year_fraction(
            start_date=settlement_date,
            end_date=row.date,
            convention=bond.day_count_convention,
            frequency=bond.frequency,
        )
        # Curve pricing formula: PV = CF * DF(t)
        price += row.total_cf * zero_curve.discount_factor(time_in_years)
    return float(price)


def macaulay_duration(bond: Bond, yield_: float, settlement_date: date) -> float:
    """Compute Macaulay duration in years.

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
        Macaulay duration in years.
    """
    price = bond.dirty_price(yield_=yield_, settlement_date=settlement_date)
    if price <= 0.0:
        return 0.0

    weighted_present_value_sum = 0.0
    future_cash_flows = bond.get_cash_flows()
    future_cash_flows = future_cash_flows[future_cash_flows["date"] > settlement_date]
    for row in future_cash_flows.itertuples(index=False):
        time_in_years = year_fraction(
            start_date=settlement_date,
            end_date=row.date,
            convention=bond.day_count_convention,
            frequency=bond.frequency,
        )
        discount_factor = (1.0 + yield_ / bond.frequency) ** (bond.frequency * time_in_years)
        present_value = row.total_cf / discount_factor
        # Macaulay duration: sum(t * PV(CF_t)) / Price
        weighted_present_value_sum += time_in_years * present_value
    return float(weighted_present_value_sum / price)


def modified_duration(bond: Bond, yield_: float, settlement_date: date) -> float:
    """Compute modified duration.

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
        Modified duration.
    """
    macaulay = macaulay_duration(bond=bond, yield_=yield_, settlement_date=settlement_date)
    # Modified duration: Macaulay / (1 + y / m)
    return float(macaulay / (1.0 + yield_ / bond.frequency))


def effective_duration(
    bond: Bond,
    zero_curve: ZeroCurve,
    settlement_date: date,
    bump_bps: float = 1.0,
) -> float:
    """Compute effective duration from full curve repricing.

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
        Effective duration.
    """
    bump = bump_bps * BASIS_POINT
    base_price = price_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    if base_price <= 0.0:
        return 0.0
    down_curve = zero_curve.bumped_parallel(-bump)
    up_curve = zero_curve.bumped_parallel(bump)
    price_down = price_from_curve(bond=bond, zero_curve=down_curve, settlement_date=settlement_date)
    price_up = price_from_curve(bond=bond, zero_curve=up_curve, settlement_date=settlement_date)
    # Effective duration: (P_down - P_up) / (2 * P * bump)
    return float((price_down - price_up) / (2.0 * base_price * bump))

