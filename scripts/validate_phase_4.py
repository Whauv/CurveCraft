"""Validation script for Phase 4 duration, convexity, and DV01."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fixed_income.analytics.convexity import convexity, effective_convexity
from fixed_income.analytics.duration import effective_duration, macaulay_duration, modified_duration
from fixed_income.analytics.dv01 import dv01, dv01_from_curve
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument

SETTLEMENT_DATE = date(2025, 1, 1)


def sample_curve():
    """Return the sample Phase 3 zero curve."""
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
    """Run the required Phase 4 validation checks."""
    bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.06,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    yield_ = 0.06

    macaulay = macaulay_duration(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)
    modified = modified_duration(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)
    bond_dv01 = dv01(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)
    bond_convexity = convexity(bond=bond, yield_=yield_, settlement_date=SETTLEMENT_DATE)

    print(f"Macaulay duration: {macaulay:.10f}")
    print(f"Modified duration: {modified:.10f}")
    print(f"DV01 per 1000 face: {bond_dv01:.10f}")
    print(f"Convexity: {bond_convexity:.10f}")
    print("Note: convexity is reported in standard years^2 units, so 68.77 corresponds to 0.6877 if scaled by 1/100.")

    if abs(macaulay - 7.6616410710) > 1e-6:
        raise SystemExit("Macaulay duration validation failed.")
    if abs(modified - 7.4384864767) > 1e-6:
        raise SystemExit("Modified duration validation failed.")
    if abs(bond_dv01 - 0.7438486477) > 1e-6:
        raise SystemExit("DV01 validation failed.")
    if bond_convexity <= 0.0:
        raise SystemExit("Convexity positivity validation failed.")

    zero_curve = sample_curve()
    effective_dur = effective_duration(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    effective_cvx = effective_convexity(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)
    curve_dv01 = dv01_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)

    print(f"Effective duration: {effective_dur:.10f}")
    print(f"Effective convexity: {effective_cvx:.10f}")
    print(f"Curve DV01 per 1000 face: {curve_dv01:.10f}")

    if effective_dur <= 0.0 or effective_cvx <= 0.0 or curve_dv01 <= 0.0:
        raise SystemExit("Curve-based risk validation failed.")

    print("Phase 4 validation passed.")


if __name__ == "__main__":
    main()
