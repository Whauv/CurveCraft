"""Validation script for Phase 5 key rate DV01."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fixed_income.analytics.dv01 import dv01_from_curve
from fixed_income.analytics.key_rate_dv01 import key_rate_dv01
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
    """Run the required Phase 5 validation checks."""
    bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    zero_curve = sample_curve()

    key_rate_map, key_rate_series = key_rate_dv01(
        bond=bond,
        zero_curve=zero_curve,
        settlement_date=SETTLEMENT_DATE,
    )
    total_curve_dv01 = dv01_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)

    print("Key rate DV01 profile:")
    for tenor, value in key_rate_map.items():
        print(f"  {tenor:>5.2f}Y -> {value:.10f}")

    print(f"Total curve DV01: {total_curve_dv01:.10f}")
    print(f"Sum of key rate DV01s: {key_rate_series.sum():.10f}")

    if abs(key_rate_series.sum() - total_curve_dv01) / total_curve_dv01 > 0.05:
        raise SystemExit("Key rate DV01 sum validation failed.")

    print("Phase 5 validation passed.")


if __name__ == "__main__":
    main()
