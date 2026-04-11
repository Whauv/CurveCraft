"""Core bond instrument implementations."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import date

import pandas as pd
from scipy.optimize import brentq, newton

from fixed_income.utils.day_count import (
    SUPPORTED_DAY_COUNT_CONVENTIONS,
    year_fraction,
)
from fixed_income.utils.schedule import generate_coupon_schedule

PAR_PRICE_TOLERANCE = 1e-10
BRENT_LOWER_BOUND = 0.0001
BRENT_UPPER_BOUND = 0.9999
NEWTON_INITIAL_GUESS = 0.05
YIELD_SOLVER_TOLERANCE = 1e-12
YIELD_SOLVER_MAX_ITERATIONS = 100


@dataclass(slots=True)
class Bond(ABC):
    """Abstract base class for fixed income instruments with deterministic cash flows.

    Parameters
    ----------
    face_value : float
        Redemption value paid at maturity.
    coupon_rate : float
        Annual coupon rate expressed as a decimal.
    maturity_date : date
        Final maturity date.
    issue_date : date
        Bond issue date.
    frequency : int
        Coupon payments per year. Supported values are 1, 2, or 4.
    day_count_convention : str
        Day count convention used for accrual and discounting.
    """

    face_value: float
    coupon_rate: float
    maturity_date: date
    issue_date: date
    frequency: int
    day_count_convention: str = "ACT/ACT"

    def __post_init__(self) -> None:
        """Validate bond inputs."""
        supported_frequencies = {1, 2, 4}
        if self.face_value <= 0.0:
            raise ValueError("face_value must be positive.")
        if self.coupon_rate < 0.0:
            raise ValueError("coupon_rate must be non-negative.")
        if self.issue_date >= self.maturity_date:
            raise ValueError("issue_date must be earlier than maturity_date.")
        if self.frequency not in supported_frequencies:
            raise ValueError(f"frequency must be one of {sorted(supported_frequencies)}.")
        if self.day_count_convention not in SUPPORTED_DAY_COUNT_CONVENTIONS:
            raise ValueError(
                "Unsupported day count convention. "
                f"Expected one of {sorted(SUPPORTED_DAY_COUNT_CONVENTIONS)}."
            )

    @property
    def coupon_amount(self) -> float:
        """Return the fixed coupon payment per period."""
        return self.face_value * self.coupon_rate / self.frequency

    def payment_dates(self) -> list[date]:
        """Return the adjusted coupon payment dates."""
        return generate_coupon_schedule(
            issue_date=self.issue_date,
            maturity_date=self.maturity_date,
            frequency=self.frequency,
        )

    def get_cash_flows(self) -> pd.DataFrame:
        """Return the scheduled cash flows.

        Returns
        -------
        pd.DataFrame
            Cash flow table with columns ``date``, ``coupon``, ``principal``, and ``total_cf``.
        """
        payment_dates = self.payment_dates()
        coupons = [self.coupon_amount] * len(payment_dates)
        principals = [0.0] * len(payment_dates)
        principals[-1] = self.face_value
        cash_flows = pd.DataFrame(
            {
                "date": payment_dates,
                "coupon": coupons,
                "principal": principals,
            }
        )
        cash_flows["total_cf"] = cash_flows["coupon"] + cash_flows["principal"]
        return cash_flows

    def accrued_interest(self, settlement_date: date) -> float:
        """Compute accrued coupon interest at settlement.

        Parameters
        ----------
        settlement_date : date
            Valuation or settlement date.

        Returns
        -------
        float
            Accrued interest from the last coupon date up to settlement.
        """
        if settlement_date <= self.issue_date:
            return 0.0
        if settlement_date >= self.maturity_date:
            return 0.0

        previous_coupon, next_coupon = self._coupon_period_bounds(settlement_date)
        accrual_fraction = year_fraction(
            start_date=previous_coupon,
            end_date=settlement_date,
            convention=self.day_count_convention,
            frequency=self.frequency,
        )
        period_fraction = year_fraction(
            start_date=previous_coupon,
            end_date=next_coupon,
            convention=self.day_count_convention,
            frequency=self.frequency,
        )
        if abs(period_fraction) < PAR_PRICE_TOLERANCE:
            return 0.0
        return self.coupon_amount * accrual_fraction / period_fraction

    def dirty_price(self, yield_: float, settlement_date: date) -> float:
        """Compute the full price from a street-convention yield.

        Parameters
        ----------
        yield_ : float
            Annualized yield to maturity expressed as a decimal.
        settlement_date : date
            Valuation or settlement date.

        Returns
        -------
        float
            Dirty price including accrued interest.
        """
        if yield_ < -1.0:
            raise ValueError("yield_ must be greater than -100%.")

        future_cash_flows = self.get_cash_flows()
        future_cash_flows = future_cash_flows[future_cash_flows["date"] > settlement_date]
        if future_cash_flows.empty:
            return 0.0

        accrued_fraction = self._accrual_fraction_in_period(settlement_date=settlement_date)
        price = 0.0
        for cash_flow_index, row in enumerate(future_cash_flows.itertuples(index=False), start=1):
            periods = cash_flow_index - accrued_fraction
            # Standard periodic discounting: PV = CF / (1 + y / m) ** (m * t)
            discount_factor = (1.0 + yield_ / self.frequency) ** periods
            price += row.total_cf / discount_factor
        return price

    def clean_price(self, yield_: float, settlement_date: date) -> float:
        """Compute the quoted clean price.

        Parameters
        ----------
        yield_ : float
            Annualized yield to maturity expressed as a decimal.
        settlement_date : date
            Valuation or settlement date.

        Returns
        -------
        float
            Clean price excluding accrued interest.
        """
        return self.dirty_price(yield_=yield_, settlement_date=settlement_date) - self.accrued_interest(
            settlement_date=settlement_date
        )

    def yield_to_maturity(self, dirty_price: float, settlement_date: date) -> float:
        """Solve for the bond's yield to maturity from dirty price.

        Parameters
        ----------
        dirty_price : float
            Observed dirty price.
        settlement_date : date
            Valuation or settlement date.

        Returns
        -------
        float
            Annualized yield to maturity expressed as a decimal.
        """
        if dirty_price <= 0.0:
            raise ValueError("dirty_price must be positive.")

        def objective(yield_: float) -> float:
            return self.dirty_price(yield_=yield_, settlement_date=settlement_date) - dirty_price

        try:
            return brentq(
                objective,
                BRENT_LOWER_BOUND,
                BRENT_UPPER_BOUND,
                xtol=YIELD_SOLVER_TOLERANCE,
                maxiter=YIELD_SOLVER_MAX_ITERATIONS,
            )
        except ValueError:
            derivative_step = 1e-6

            def derivative(yield_: float) -> float:
                price_up = self.dirty_price(yield_=yield_ + derivative_step, settlement_date=settlement_date)
                price_down = self.dirty_price(
                    yield_=max(yield_ - derivative_step, 0.0),
                    settlement_date=settlement_date,
                )
                return (price_up - price_down) / (2.0 * derivative_step)

            return float(
                newton(
                    objective,
                    x0=max(self.coupon_rate, NEWTON_INITIAL_GUESS),
                    fprime=derivative,
                    tol=YIELD_SOLVER_TOLERANCE,
                    maxiter=YIELD_SOLVER_MAX_ITERATIONS,
                )
            )

    def ytm(self, dirty_price: float, settlement_date: date) -> float:
        """Alias for :meth:`yield_to_maturity`."""
        return self.yield_to_maturity(dirty_price=dirty_price, settlement_date=settlement_date)

    def _coupon_period_bounds(self, settlement_date: date) -> tuple[date, date]:
        """Return previous and next coupon dates bracketing settlement."""
        payment_dates = self.payment_dates()
        if settlement_date < payment_dates[0]:
            return self.issue_date, payment_dates[0]

        previous_coupon = self.issue_date
        next_coupon = payment_dates[0]
        for payment_date in payment_dates:
            if settlement_date < payment_date:
                next_coupon = payment_date
                break
            previous_coupon = payment_date
        else:
            next_coupon = self.maturity_date

        return previous_coupon, next_coupon

    def _accrual_fraction_in_period(self, settlement_date: date) -> float:
        """Return the elapsed fraction of the current coupon period."""
        if settlement_date <= self.issue_date or settlement_date >= self.maturity_date:
            return 0.0

        previous_coupon, next_coupon = self._coupon_period_bounds(settlement_date)
        elapsed = year_fraction(
            start_date=previous_coupon,
            end_date=settlement_date,
            convention=self.day_count_convention,
            frequency=self.frequency,
        )
        period = year_fraction(
            start_date=previous_coupon,
            end_date=next_coupon,
            convention=self.day_count_convention,
            frequency=self.frequency,
        )
        if abs(period) < PAR_PRICE_TOLERANCE:
            return 0.0
        return elapsed / period


@dataclass(slots=True)
class FixedRateBond(Bond):
    """Plain-vanilla fixed-rate coupon bond."""
