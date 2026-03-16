"""Zero curve representation and rate analytics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fixed_income.curves.interpolation import (
    BaseInterpolator,
    CubicSplineInterpolator,
    LinearInterpolator,
    LogLinearInterpolator,
)

INTERPOLATOR_MAP = {
    "linear": LinearInterpolator,
    "log_linear": LogLinearInterpolator,
    "cubic_spline": CubicSplineInterpolator,
}
MIN_TIME = 1e-10


@dataclass(slots=True)
class ZeroCurve:
    """Zero curve built from discount factors."""

    maturities: np.ndarray
    discount_factors: np.ndarray
    interpolation_method: str = "cubic_spline"
    _interpolator: BaseInterpolator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate inputs and initialize the interpolator."""
        maturities = np.asarray(self.maturities, dtype=float)
        discount_factors = np.asarray(self.discount_factors, dtype=float)
        if maturities.ndim != 1 or discount_factors.ndim != 1:
            raise ValueError("Curve inputs must be one-dimensional arrays.")
        if len(maturities) != len(discount_factors):
            raise ValueError("Curve inputs must have the same length.")
        if len(maturities) < 2:
            raise ValueError("ZeroCurve requires at least two nodes.")
        if maturities[0] != 0.0:
            raise ValueError("ZeroCurve must include t=0 with discount factor 1.0.")
        if not np.isclose(discount_factors[0], 1.0):
            raise ValueError("Discount factor at t=0 must equal 1.0.")
        if not np.all(np.diff(maturities) > 0.0):
            raise ValueError("Maturities must be strictly increasing.")
        if np.any(discount_factors <= 0.0):
            raise ValueError("Discount factors must be strictly positive.")
        if self.interpolation_method not in INTERPOLATOR_MAP:
            raise ValueError(
                f"Unsupported interpolation method: {self.interpolation_method}. "
                f"Expected one of {sorted(INTERPOLATOR_MAP)}."
            )

        self.maturities = maturities
        self.discount_factors = discount_factors
        log_discount_factors = np.log(discount_factors)
        interpolator_class = INTERPOLATOR_MAP[self.interpolation_method]
        self._interpolator = interpolator_class(
            x=self.maturities,
            y=log_discount_factors,
        )

    def discount_factor(self, t: float) -> float:
        """Return the interpolated discount factor at maturity ``t``."""
        if t < 0.0:
            raise ValueError("Maturity t must be non-negative.")
        if np.isclose(t, 0.0):
            return 1.0
        log_df = float(self._interpolator.interpolate(np.array([t]))[0])
        return float(np.exp(log_df))

    def spot_rate(self, t: float) -> float:
        """Return the continuously compounded spot rate."""
        if t < 0.0:
            raise ValueError("Maturity t must be non-negative.")
        if np.isclose(t, 0.0):
            return 0.0
        discount_factor = self.discount_factor(t)
        return float(-np.log(discount_factor) / max(t, MIN_TIME))

    def forward_rate(self, t1: float, t2: float) -> float:
        """Return the continuously compounded forward rate between ``t1`` and ``t2``."""
        if t1 < 0.0 or t2 < 0.0:
            raise ValueError("Forward rate maturities must be non-negative.")
        if t2 <= t1:
            raise ValueError("t2 must be greater than t1.")
        df1 = self.discount_factor(t1)
        df2 = self.discount_factor(t2)
        return float(np.log(df1 / df2) / (t2 - t1))

    def par_rate(self, maturity: float, frequency: int = 1) -> float:
        """Return the annualized par coupon rate for a maturity."""
        if maturity <= 0.0:
            raise ValueError("Maturity must be positive.")
        if frequency <= 0:
            raise ValueError("frequency must be positive.")
        periods = int(round(maturity * frequency))
        if not np.isclose(periods / frequency, maturity):
            raise ValueError("Maturity must align with the requested payment frequency.")

        payment_times = np.arange(1, periods + 1, dtype=float) / frequency
        annuity = np.sum((1.0 / frequency) * np.array([self.discount_factor(t) for t in payment_times]))
        final_df = self.discount_factor(maturity)
        # Standard par swap/bond relationship: c = (1 - DF(T)) / sum(alpha_i * DF(t_i))
        return float((1.0 - final_df) / annuity)

    def bumped_parallel(self, bump: float) -> "ZeroCurve":
        """Return a curve with all continuously compounded spot rates shifted in parallel."""
        bumped_discount_factors = np.array(
            [
                1.0 if np.isclose(t, 0.0) else df * np.exp(-bump * t)
                for t, df in zip(self.maturities, self.discount_factors, strict=True)
            ],
            dtype=float,
        )
        return ZeroCurve(
            maturities=self.maturities.copy(),
            discount_factors=bumped_discount_factors,
            interpolation_method=self.interpolation_method,
        )
