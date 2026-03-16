"""Validation script for Phase 1 and Phase 2 bond pricing checks."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fixed_income.bonds.bond import FixedRateBond

FACE_VALUE = 1000.0
COUPON_RATE = 0.04
SETTLEMENT_DATE = date(2025, 1, 1)


def main() -> None:
    """Run the required Phase 1 validation checks."""
    bond = FixedRateBond(
        face_value=FACE_VALUE,
        coupon_rate=COUPON_RATE,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )

    par_price = bond.dirty_price(yield_=0.04, settlement_date=SETTLEMENT_DATE)
    high_yield_price = bond.dirty_price(yield_=0.05, settlement_date=SETTLEMENT_DATE)
    low_yield_price = bond.dirty_price(yield_=0.03, settlement_date=SETTLEMENT_DATE)

    print(f"Par bond check (4% coupon, 4% yield): {par_price:.2f}")
    print(f"Price at 5% yield: {high_yield_price:.6f}")
    print(f"Price at 3% yield: {low_yield_price:.6f}")

    if round(par_price, 2) != FACE_VALUE:
        raise SystemExit("Par bond validation failed.")
    if not (low_yield_price > par_price > high_yield_price):
        raise SystemExit("Price-yield inverse relationship validation failed.")

    par_ytm = bond.yield_to_maturity(dirty_price=1000.0, settlement_date=SETTLEMENT_DATE)
    discount_ytm = bond.yield_to_maturity(dirty_price=950.0, settlement_date=SETTLEMENT_DATE)
    premium_ytm = bond.yield_to_maturity(dirty_price=1050.0, settlement_date=SETTLEMENT_DATE)

    roundtrip_price = bond.dirty_price(yield_=discount_ytm, settlement_date=SETTLEMENT_DATE)

    print(f"Par bond YTM from price 1000.00: {par_ytm:.10f}")
    print(f"Discount bond YTM from price 950.00: {discount_ytm:.10f}")
    print(f"Premium bond YTM from price 1050.00: {premium_ytm:.10f}")
    print(f"Round-trip price from discount YTM: {roundtrip_price:.10f}")

    if abs(par_ytm - COUPON_RATE) > 1e-10:
        raise SystemExit("Par bond YTM validation failed.")
    if discount_ytm <= COUPON_RATE:
        raise SystemExit("Discount bond YTM validation failed.")
    if premium_ytm >= COUPON_RATE:
        raise SystemExit("Premium bond YTM validation failed.")
    if abs(roundtrip_price - 950.0) > 1e-6:
        raise SystemExit("YTM round-trip validation failed.")

    print("Phase 1 and Phase 2 validation passed.")


if __name__ == "__main__":
    main()
