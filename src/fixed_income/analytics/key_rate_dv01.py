"""Key rate DV01 analytics."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve

from .duration import BASIS_POINT, price_from_curve

STANDARD_TENOR_BUCKETS = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]


def key_rate_dv01(
    bond: Bond,
    zero_curve: ZeroCurve,
    settlement_date: date,
    bump_bps: float = 1.0,
    tenor_buckets: list[float] | None = None,
) -> tuple[dict[float, float], pd.Series]:
    """Compute key rate DV01 values across standard tenor buckets.

    Parameters
    ----------
    bond : Bond
        Bond to analyze.
    zero_curve : ZeroCurve
        Base zero curve.
    settlement_date : date
        Valuation or settlement date.
    bump_bps : float, optional
        Node bump size in basis points.
    tenor_buckets : list[float] | None, optional
        Custom tenor buckets in years. Defaults to the standard buckets.

    Returns
    -------
    tuple[dict[float, float], pd.Series]
        Key-rate DV01 values as both a dictionary and a pandas Series.
    """
    buckets = tenor_buckets if tenor_buckets is not None else STANDARD_TENOR_BUCKETS
    if not buckets:
        raise ValueError("At least one tenor bucket is required.")

    bump = bump_bps * BASIS_POINT
    base_price = price_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    if base_price <= 0.0:
        empty_series = pd.Series(dtype=float)
        return {}, empty_series

    bucket_curve = _curve_on_buckets(zero_curve=zero_curve, buckets=buckets)
    key_rate_values: dict[float, float] = {}

    for bucket in buckets:
        shifted_curve = _bump_single_bucket(zero_curve=bucket_curve, bucket=bucket, bump=bump)
        shifted_price = price_from_curve(bond=bond, zero_curve=shifted_curve, settlement_date=settlement_date)
        key_rate_values[float(bucket)] = float(base_price - shifted_price)

    series = pd.Series(key_rate_values, name="key_rate_dv01", dtype=float)
    series.index.name = "tenor_years"
    return key_rate_values, series


def _curve_on_buckets(zero_curve: ZeroCurve, buckets: list[float]) -> ZeroCurve:
    """Project a curve onto the requested tenor buckets using spot rates."""
    node_times = np.array([0.0, *sorted(float(bucket) for bucket in buckets)], dtype=float)
    spot_rates = np.array([0.0 if np.isclose(t, 0.0) else zero_curve.spot_rate(float(t)) for t in node_times], dtype=float)
    discount_factors = np.exp(-spot_rates * node_times)
    discount_factors[0] = 1.0
    return ZeroCurve(
        maturities=node_times,
        discount_factors=discount_factors,
        interpolation_method="cubic_spline",
    )


def _bump_single_bucket(zero_curve: ZeroCurve, bucket: float, bump: float) -> ZeroCurve:
    """Return a curve with a single tenor node bumped."""
    node_times = zero_curve.maturities.copy()
    spot_rates = np.array(
        [0.0 if np.isclose(t, 0.0) else zero_curve.spot_rate(float(t)) for t in node_times],
        dtype=float,
    )
    bucket_index = int(np.where(np.isclose(node_times, bucket))[0][0])
    spot_rates[bucket_index] += bump
    discount_factors = np.exp(-spot_rates * node_times)
    discount_factors[0] = 1.0
    return ZeroCurve(
        maturities=node_times,
        discount_factors=discount_factors,
        interpolation_method="cubic_spline",
    )
