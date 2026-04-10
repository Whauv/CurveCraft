"""Yield curve bootstrapper for deposits and swaps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from fixed_income.curves.zero_curve import ZeroCurve

MONTHS_IN_YEAR = 12.0
DEPOSIT_DENOMINATOR = 360.0
SWAP_FIXED_FREQUENCY = 1
ROOT_LOWER_BOUND = 1e-8
ROOT_UPPER_BOUND = 1.0
ROOT_TOLERANCE = 1e-14
ROOT_MAX_ITERATIONS = 100
SUPPORTED_INSTRUMENT_TYPES = {"deposit", "fra", "swap"}
TENOR_TO_MONTHS = {
    "1M": 1,
    "3M": 3,
    "6M": 6,
    "1Y": 12,
    "2Y": 24,
    "3Y": 36,
    "5Y": 60,
    "7Y": 84,
    "10Y": 120,
    "20Y": 240,
    "30Y": 360,
}


@dataclass(slots=True)
class MarketInstrument:
    """Market quote used for zero curve construction."""

    instrument_type: str
    tenor: str
    rate: float
    settlement_days: int = 2

    def __post_init__(self) -> None:
        """Validate the market instrument."""
        if self.instrument_type not in SUPPORTED_INSTRUMENT_TYPES:
            raise ValueError(
                f"Unsupported instrument_type: {self.instrument_type}. "
                f"Expected one of {sorted(SUPPORTED_INSTRUMENT_TYPES)}."
            )
        if self.instrument_type == "fra":
            raise NotImplementedError("FRA bootstrapping is not implemented in Phase 3.")
        if self.tenor not in TENOR_TO_MONTHS:
            raise ValueError(f"Unsupported tenor: {self.tenor}")
        if self.rate <= -1.0:
            raise ValueError("Market rate must be greater than -100%.")

    @property
    def maturity_in_years(self) -> float:
        """Return the tenor expressed in years."""
        return TENOR_TO_MONTHS[self.tenor] / MONTHS_IN_YEAR


class Bootstrapper:
    """Bootstrap a zero curve from deposit and par swap quotes."""

    def __init__(self, instruments: list[MarketInstrument]) -> None:
        if not instruments:
            raise ValueError("At least one market instrument is required.")
        self.instruments = sorted(instruments, key=lambda instrument: instrument.maturity_in_years)

    def bootstrap(self, interpolation_method: str = "cubic_spline") -> ZeroCurve:
        """Bootstrap a zero curve from the supplied market instruments."""
        discount_factor_map: dict[float, float] = {0.0: 1.0}

        for instrument in self.instruments:
            maturity = instrument.maturity_in_years
            if instrument.instrument_type == "deposit":
                year_fraction = self._deposit_year_fraction(instrument.tenor)
                # Deposit bootstrap: DF(t) = 1 / (1 + r * tau)
                discount_factor_map[maturity] = 1.0 / (1.0 + instrument.rate * year_fraction)
                continue

            if instrument.instrument_type == "swap":
                discount_factor_map[maturity] = self._bootstrap_swap_discount_factor(
                    maturity=maturity,
                    swap_rate=instrument.rate,
                    discount_factor_map=discount_factor_map,
                )
                continue

        maturities = np.array(sorted(discount_factor_map), dtype=float)
        discount_factors = np.array([discount_factor_map[t] for t in maturities], dtype=float)
        return ZeroCurve(
            maturities=maturities,
            discount_factors=discount_factors,
            interpolation_method=interpolation_method,
        )

    def _bootstrap_swap_discount_factor(
        self,
        maturity: float,
        swap_rate: float,
        discount_factor_map: dict[float, float],
    ) -> float:
        """Solve for the final discount factor of a par fixed-for-floating swap."""
        payment_times = np.arange(1, int(round(maturity * SWAP_FIXED_FREQUENCY)) + 1, dtype=float)

        def objective(candidate_df: float) -> float:
            coupon_leg = 0.0
            for payment_time in payment_times[:-1]:
                implied_df = self._discount_factor_with_candidate(
                    target_time=payment_time,
                    candidate_time=maturity,
                    candidate_df=candidate_df,
                    discount_factor_map=discount_factor_map,
                )
                coupon_leg += (swap_rate / SWAP_FIXED_FREQUENCY) * implied_df
            coupon_leg += (swap_rate / SWAP_FIXED_FREQUENCY) * candidate_df
            # Par swap equation: sum(coupon * DF(t_i)) + DF(T) = 1
            return coupon_leg + candidate_df - 1.0

        return float(
            brentq(
                objective,
                ROOT_LOWER_BOUND,
                ROOT_UPPER_BOUND,
                xtol=ROOT_TOLERANCE,
                maxiter=ROOT_MAX_ITERATIONS,
            )
        )

    @staticmethod
    def _deposit_year_fraction(tenor: str) -> float:
        """Return the ACT/360-style year fraction used for deposit quotes."""
        months = TENOR_TO_MONTHS[tenor]
        if months == 12:
            return 1.0
        return (months * 30.0) / DEPOSIT_DENOMINATOR

    @staticmethod
    def _discount_factor_with_candidate(
        target_time: float,
        candidate_time: float,
        candidate_df: float,
        discount_factor_map: dict[float, float],
    ) -> float:
        """Infer discount factors between known nodes using piecewise log-linear interpolation."""
        nodes = {**discount_factor_map, candidate_time: candidate_df}
        if target_time in nodes:
            return nodes[target_time]

        times = sorted(nodes)
        lower_time = max(time for time in times if time < target_time)
        upper_time = min(time for time in times if time > target_time)
        lower_df = nodes[lower_time]
        upper_df = nodes[upper_time]

        weight = (target_time - lower_time) / (upper_time - lower_time)
        log_df = np.log(lower_df) + weight * (np.log(upper_df) - np.log(lower_df))
        return float(np.exp(log_df))
