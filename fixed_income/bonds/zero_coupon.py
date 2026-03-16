"""Zero coupon bond implementation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from fixed_income.bonds.bond import Bond
from fixed_income.utils.day_count import year_fraction


class ZeroCouponBond(Bond):
    """Zero coupon bond with a single redemption cash flow."""

    def __init__(
        self,
        face_value: float,
        maturity_date: date,
        issue_date: date,
        day_count_convention: str = "ACT/ACT",
    ) -> None:
        super().__init__(
            face_value=face_value,
            coupon_rate=0.0,
            maturity_date=maturity_date,
            issue_date=issue_date,
            frequency=1,
            day_count_convention=day_count_convention,
        )

    def get_cash_flows(self) -> pd.DataFrame:
        """Return the zero coupon cash flow table."""
        return pd.DataFrame(
            {
                "date": [self.maturity_date],
                "coupon": [0.0],
                "principal": [self.face_value],
                "total_cf": [self.face_value],
            }
        )

    def accrued_interest(self, settlement_date: date) -> float:
        """Zero coupon bonds do not accrue periodic coupon interest."""
        return 0.0

    def dirty_price(self, yield_: float, settlement_date: date) -> float:
        """Compute the present value of the redemption payment."""
        if settlement_date >= self.maturity_date:
            return 0.0
        time_in_years = year_fraction(
            start_date=settlement_date,
            end_date=self.maturity_date,
            convention=self.day_count_convention,
            frequency=self.frequency,
        )
        # Standard annual compounding for a single redemption payment.
        return self.face_value / ((1.0 + yield_) ** time_in_years)
