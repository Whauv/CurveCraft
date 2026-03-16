"""Validation script for Phase 3 zero curve bootstrapping."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument


def sample_instruments() -> list[MarketInstrument]:
    """Return the Phase 3 sample market quotes."""
    return [
        MarketInstrument(instrument_type="deposit", tenor="1M", rate=0.0500, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="3M", rate=0.0510, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="6M", rate=0.0515, settlement_days=2),
        MarketInstrument(instrument_type="deposit", tenor="1Y", rate=0.0520, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="2Y", rate=0.0525, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="5Y", rate=0.0530, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="10Y", rate=0.0535, settlement_days=2),
        MarketInstrument(instrument_type="swap", tenor="30Y", rate=0.0540, settlement_days=2),
    ]


def main() -> None:
    """Run the required Phase 3 validation checks."""
    curve = Bootstrapper(sample_instruments()).bootstrap()
    repricing_curve = Bootstrapper(sample_instruments()).bootstrap(interpolation_method="log_linear")

    print("Bootstrapped nodes:")
    for maturity, discount_factor in zip(curve.maturities, curve.discount_factors):
        print(f"  t={maturity:>5.4f}, DF={discount_factor:.10f}, spot={curve.spot_rate(float(maturity)):.6%}")

    if curve.discount_factor(0.0) != 1.0:
        raise SystemExit("DF(0) validation failed.")

    if not np.all(np.diff(curve.discount_factors) < 0.0):
        raise SystemExit("Discount factor monotonicity validation failed.")

    maturities = np.linspace(0.25, 30.0, 120)
    forward_rates = [
        curve.forward_rate(float(t1), float(t2))
        for t1, t2 in zip(maturities[:-1], maturities[1:])
    ]
    if not all(rate > 0.0 for rate in forward_rates):
        raise SystemExit("Forward rate positivity validation failed.")

    swap_errors: list[float] = []
    for instrument in sample_instruments():
        if instrument.instrument_type != "swap":
            continue
        maturity = instrument.maturity_in_years
        payment_times = np.arange(1.0, maturity + 1.0, 1.0)
        coupon_leg = instrument.rate * sum(repricing_curve.discount_factor(float(t)) for t in payment_times)
        swap_value = coupon_leg + repricing_curve.discount_factor(maturity)
        swap_errors.append(abs(swap_value - 1.0))
    if max(swap_errors) > 1e-8:
        raise SystemExit("Swap repricing validation failed.")

    print(f"Minimum sampled forward rate: {min(forward_rates):.6%}")
    print(f"Maximum swap repricing error: {max(swap_errors):.10f}")
    print("Phase 3 validation passed.")


if __name__ == "__main__":
    main()
