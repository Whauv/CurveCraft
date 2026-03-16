"""Portfolio analytics for fixed income instruments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from fixed_income.analytics.convexity import effective_convexity
from fixed_income.analytics.duration import effective_duration, price_from_curve
from fixed_income.analytics.dv01 import dv01_from_curve, hedge_notional
from fixed_income.analytics.key_rate_dv01 import STANDARD_TENOR_BUCKETS, key_rate_dv01
from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve


@dataclass(slots=True)
class BondPosition:
    """Portfolio position in a bond instrument.

    Parameters
    ----------
    bond : Bond
        Bond instrument held in the portfolio.
    notional : float
        Face-value notional of the position.
    direction : int
        Position direction, ``+1`` for long and ``-1`` for short.
    """

    bond: Bond
    notional: float
    direction: int

    def __post_init__(self) -> None:
        """Validate the position."""
        if self.notional <= 0.0:
            raise ValueError("notional must be positive.")
        if self.direction not in {-1, 1}:
            raise ValueError("direction must be +1 or -1.")

    @property
    def quantity(self) -> float:
        """Return the number of face units held."""
        return self.notional / self.bond.face_value


@dataclass(slots=True)
class Portfolio:
    """Portfolio of bond positions with aggregate analytics."""

    positions: list[BondPosition] = field(default_factory=list)

    def add_position(self, bond: Bond, notional: float, direction: int) -> None:
        """Add a bond position to the portfolio."""
        self.positions.append(BondPosition(bond=bond, notional=notional, direction=direction))

    def total_market_value(self, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return total signed market value."""
        return float(
            sum(
                self._position_market_value(position=position, zero_curve=zero_curve, settlement_date=settlement_date)
                for position in self.positions
            )
        )

    def portfolio_dv01(self, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return total signed portfolio DV01."""
        return float(
            sum(
                self._position_dv01(position=position, zero_curve=zero_curve, settlement_date=settlement_date)
                for position in self.positions
            )
        )

    def portfolio_duration(self, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return DV01-weighted portfolio duration."""
        weighted_sum = 0.0
        total_weight = 0.0
        for position in self.positions:
            position_dv01 = self._position_dv01(
                position=position,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            position_duration = effective_duration(
                bond=position.bond,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            weight = abs(position_dv01)
            weighted_sum += weight * position_duration
            total_weight += weight
        if total_weight == 0.0:
            return 0.0
        return float(weighted_sum / total_weight)

    def portfolio_convexity(self, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return market-value-weighted portfolio convexity."""
        weighted_sum = 0.0
        total_weight = 0.0
        for position in self.positions:
            market_value = self._position_market_value(
                position=position,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            position_convexity = effective_convexity(
                bond=position.bond,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            weight = abs(market_value)
            weighted_sum += weight * position_convexity
            total_weight += weight
        if total_weight == 0.0:
            return 0.0
        return float(weighted_sum / total_weight)

    def key_rate_dv01_profile(self, zero_curve: ZeroCurve, settlement_date: date) -> pd.DataFrame:
        """Return a position-level key rate DV01 profile."""
        rows: list[dict[str, float | str]] = []
        total_row: dict[str, float | str] = {"name": "Total"}

        for position in self.positions:
            _, series = key_rate_dv01(
                bond=position.bond,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            scaled_series = series * position.quantity * position.direction
            row: dict[str, float | str] = {"name": self._position_name(position)}
            for tenor in STANDARD_TENOR_BUCKETS:
                row[f"{tenor:g}Y"] = float(scaled_series.loc[tenor])
            rows.append(row)

        for tenor in STANDARD_TENOR_BUCKETS:
            total_row[f"{tenor:g}Y"] = float(sum(row[f"{tenor:g}Y"] for row in rows)) if rows else 0.0
        rows.append(total_row)
        return pd.DataFrame(rows)

    def risk_report(self, zero_curve: ZeroCurve, settlement_date: date) -> pd.DataFrame:
        """Return a position-level risk report."""
        rows: list[dict[str, float | str]] = []
        for position in self.positions:
            market_value = self._position_market_value(
                position=position,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            position_dv01 = self._position_dv01(
                position=position,
                zero_curve=zero_curve,
                settlement_date=settlement_date,
            )
            rows.append(
                {
                    "CUSIP/name": self._position_name(position),
                    "notional": float(position.notional * position.direction),
                    "MV": market_value,
                    "DV01": position_dv01,
                    "duration": effective_duration(
                        bond=position.bond,
                        zero_curve=zero_curve,
                        settlement_date=settlement_date,
                    ),
                    "convexity": effective_convexity(
                        bond=position.bond,
                        zero_curve=zero_curve,
                        settlement_date=settlement_date,
                    ),
                }
            )
        return pd.DataFrame(rows, columns=["CUSIP/name", "notional", "MV", "DV01", "duration", "convexity"])

    def hedge_trade(
        self,
        target_dv01: float,
        hedge_bond: Bond,
        zero_curve: ZeroCurve,
        settlement_date: date,
    ) -> float:
        """Return hedge bond notional needed to reach a target portfolio DV01."""
        current_dv01 = self.portfolio_dv01(zero_curve=zero_curve, settlement_date=settlement_date)
        required_dv01_change = target_dv01 - current_dv01
        hedge_unit_dv01 = dv01_from_curve(
            bond=hedge_bond,
            zero_curve=zero_curve,
            settlement_date=settlement_date,
        ) / hedge_bond.face_value
        return float(hedge_notional(bond_dv01=required_dv01_change, hedge_bond_dv01=hedge_unit_dv01))

    def _position_market_value(self, position: BondPosition, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return signed position market value."""
        dirty_price = price_from_curve(
            bond=position.bond,
            zero_curve=zero_curve,
            settlement_date=settlement_date,
        )
        return float(position.direction * position.quantity * dirty_price)

    def _position_dv01(self, position: BondPosition, zero_curve: ZeroCurve, settlement_date: date) -> float:
        """Return signed position DV01."""
        unit_dv01 = dv01_from_curve(
            bond=position.bond,
            zero_curve=zero_curve,
            settlement_date=settlement_date,
        )
        return float(position.direction * position.quantity * unit_dv01)

    @staticmethod
    def _position_name(position: BondPosition) -> str:
        """Return a display name for a position."""
        return str(
            getattr(position.bond, "cusip", None)
            or getattr(position.bond, "name", None)
            or f"{position.bond.__class__.__name__}_{position.bond.maturity_date.isoformat()}"
        )
