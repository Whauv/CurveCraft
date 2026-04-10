"""Validation script for Phase 6 portfolio analytics."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fixed_income.curves.zero_curve import ZeroCurve

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SETTLEMENT_DATE = date(2025, 1, 1)


def _bootstrap_src_path() -> None:
    """Ensure the src layout is importable when running the script directly."""
    src_text = str(SRC_PATH)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)


def sample_curve() -> "ZeroCurve":
    """Return the sample Phase 3 zero curve."""
    _bootstrap_src_path()
    from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument

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


def main() -> None:
    """Run the required Phase 6 validation checks."""
    _bootstrap_src_path()
    from fixed_income.bonds.bond import FixedRateBond
    from fixed_income.portfolio.portfolio import Portfolio

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
    hedge_bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )

    portfolio = Portfolio()
    portfolio.add_position(bond=bond_one, notional=2_000_000.0, direction=1)
    portfolio.add_position(bond=bond_two, notional=1_000_000.0, direction=-1)

    total_mv = portfolio.total_market_value(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    total_dv01 = portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    weighted_duration = portfolio.portfolio_duration(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    weighted_convexity = portfolio.portfolio_convexity(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)

    print(f"Total market value: {total_mv:.6f}")
    print(f"Total DV01: {total_dv01:.6f}")
    print(f"Portfolio duration: {weighted_duration:.6f}")
    print(f"Portfolio convexity: {weighted_convexity:.6f}")
    print("\nRisk report:")
    print(portfolio.risk_report(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE).to_string(index=False))
    print("\nKey rate profile:")
    key_rate_profile = portfolio.key_rate_dv01_profile(
        zero_curve=zero_curve,
        settlement_date=SETTLEMENT_DATE,
    )
    print(key_rate_profile.to_string(index=False))

    hedge_notional = portfolio.hedge_trade(
        target_dv01=0.0,
        hedge_bond=hedge_bond,
        zero_curve=zero_curve,
        settlement_date=SETTLEMENT_DATE,
    )
    print(f"\nRequired hedge notional to reach zero DV01: {hedge_notional:.6f}")

    if weighted_duration <= 0.0 or weighted_convexity <= 0.0:
        raise SystemExit("Portfolio weighted risk validation failed.")

    hedged_portfolio = Portfolio(positions=portfolio.positions.copy())
    hedged_portfolio.add_position(
        bond=hedge_bond,
        notional=abs(hedge_notional),
        direction=1 if hedge_notional >= 0.0 else -1,
    )
    hedged_dv01 = hedged_portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    print(f"Hedged portfolio DV01: {hedged_dv01:.10f}")

    if abs(hedged_dv01) > 1e-8:
        raise SystemExit("Portfolio hedge validation failed.")

    print("Phase 6 validation passed.")


if __name__ == "__main__":
    main()
