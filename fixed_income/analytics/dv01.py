"""DV01 analytics for fixed income instruments."""

from __future__ import annotations

from datetime import date

from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve

from .duration import BASIS_POINT, modified_duration, price_from_curve


def dv01(bond: Bond, yield_: float, settlement_date: date) -> float:
    """Compute DV01 from modified duration and dirty price.

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
        Dollar value of a one basis point move.
    """
    dirty_price = bond.dirty_price(yield_=yield_, settlement_date=settlement_date)
    duration_value = modified_duration(bond=bond, yield_=yield_, settlement_date=settlement_date)
    # DV01: modified_duration * dirty_price * 0.0001
    return float(duration_value * dirty_price * BASIS_POINT)


def dv01_from_curve(bond: Bond, zero_curve: ZeroCurve, settlement_date: date) -> float:
    """Compute DV01 from full curve repricing under a parallel shift.

    Parameters
    ----------
    bond : Bond
        Bond to analyze.
    zero_curve : ZeroCurve
        Base zero curve.
    settlement_date : date
        Valuation or settlement date.

    Returns
    -------
    float
        Dollar value of a one basis point move from curve repricing.
    """
    base_price = price_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    shifted_curve = zero_curve.bumped_parallel(BASIS_POINT)
    shifted_price = price_from_curve(bond=bond, zero_curve=shifted_curve, settlement_date=settlement_date)
    return float(base_price - shifted_price)


def hedge_notional(bond_dv01: float, hedge_bond_dv01: float) -> float:
    """Return the hedge notional ratio needed to offset DV01.

    Parameters
    ----------
    bond_dv01 : float
        DV01 of the position being hedged.
    hedge_bond_dv01 : float
        DV01 of the hedge instrument.

    Returns
    -------
    float
        Hedge notional ratio.
    """
    if hedge_bond_dv01 == 0.0:
        raise ValueError("hedge_bond_dv01 must be non-zero.")
    # Hedge ratio: bond_dv01 / hedge_bond_dv01
    return float(bond_dv01 / hedge_bond_dv01)
