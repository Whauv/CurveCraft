"""Generate README chart assets for the fixed income project."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fixed_income.analytics.key_rate_dv01 import key_rate_dv01
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument
from fixed_income.portfolio.portfolio import Portfolio
from fixed_income.visualization.plots import (
    plot_key_rate_dv01,
    plot_portfolio_risk,
    plot_price_yield,
    plot_yield_curve,
)

OUTPUT_DIR = PROJECT_ROOT / "docs" / "images"
SETTLEMENT_DATE = date(2025, 1, 1)


def sample_curve():
    """Return the sample zero curve."""
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
    """Generate static chart images for the README."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zero_curve = sample_curve()
    bond = FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.05,
        issue_date=SETTLEMENT_DATE,
        maturity_date=date(2035, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )
    portfolio = Portfolio()
    portfolio.add_position(bond=bond, notional=2_000_000.0, direction=1)
    portfolio.add_position(
        FixedRateBond(
            face_value=1000.0,
            coupon_rate=0.04,
            issue_date=SETTLEMENT_DATE,
            maturity_date=date(2029, 1, 1),
            frequency=2,
            day_count_convention="ACT/ACT",
        ),
        notional=1_000_000.0,
        direction=-1,
    )

    _, key_rate_series = key_rate_dv01(bond=bond, zero_curve=zero_curve, settlement_date=SETTLEMENT_DATE)

    figures = {
        "yield_curve.png": plot_yield_curve(zero_curve),
        "price_yield.png": plot_price_yield(bond, settlement_date=SETTLEMENT_DATE),
        "key_rate_dv01.png": plot_key_rate_dv01(key_rate_series),
        "portfolio_risk.png": plot_portfolio_risk(portfolio, zero_curve, SETTLEMENT_DATE),
    }
    for filename, figure in figures.items():
        figure.write_image(OUTPUT_DIR / filename, width=1200, height=700, scale=2)


if __name__ == "__main__":
    main()
