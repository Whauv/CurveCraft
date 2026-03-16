"""Phase 7 visualization tests."""

from __future__ import annotations

from datetime import date

from fixed_income.analytics.key_rate_dv01 import key_rate_dv01
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument
from fixed_income.portfolio.portfolio import Portfolio
from fixed_income.visualization.plots import (
    plot_cash_flows,
    plot_key_rate_dv01,
    plot_portfolio_risk,
    plot_price_yield,
    plot_yield_curve,
)

SETTLEMENT_DATE = date(2025, 1, 1)


def sample_curve():
    """Return a representative zero curve for visualization tests."""
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


def sample_bond() -> FixedRateBond:
    """Return a representative bond for visualization tests."""
    return FixedRateBond(
        face_value=1000.0,
        coupon_rate=0.05,
        issue_date=date(2025, 1, 1),
        maturity_date=date(2032, 1, 1),
        frequency=2,
        day_count_convention="ACT/ACT",
    )


def test_plot_yield_curve_has_three_traces() -> None:
    """Yield curve plot should contain spot, forward, and par traces."""
    figure = plot_yield_curve(sample_curve())
    assert len(figure.data) == 3


def test_plot_price_yield_contains_curve_and_tangent() -> None:
    """Price-yield plot should include the price curve and tangent line."""
    figure = plot_price_yield(sample_bond(), settlement_date=SETTLEMENT_DATE)
    assert len(figure.data) == 3
    assert figure.data[0].name == "Clean Price"
    assert figure.data[1].name == "Duration Tangent"


def test_plot_key_rate_dv01_is_bar_chart() -> None:
    """Key-rate DV01 plot should be a single bar chart."""
    _, series = key_rate_dv01(sample_bond(), sample_curve(), SETTLEMENT_DATE)
    figure = plot_key_rate_dv01(series)
    assert len(figure.data) == 1
    assert figure.data[0].type == "bar"


def test_plot_cash_flows_is_stacked() -> None:
    """Cash flow plot should contain coupon and principal bar traces."""
    figure = plot_cash_flows(sample_bond(), settlement_date=SETTLEMENT_DATE)
    assert len(figure.data) == 2
    assert figure.layout.barmode == "stack"


def test_plot_portfolio_risk_matches_position_count() -> None:
    """Portfolio risk plot should contain one trace per non-total position."""
    portfolio = Portfolio()
    portfolio.add_position(sample_bond(), 2_000_000.0, 1)
    portfolio.add_position(
        FixedRateBond(
            face_value=1000.0,
            coupon_rate=0.04,
            issue_date=date(2025, 1, 1),
            maturity_date=date(2029, 1, 1),
            frequency=2,
            day_count_convention="ACT/ACT",
        ),
        1_000_000.0,
        -1,
    )
    figure = plot_portfolio_risk(portfolio, sample_curve(), SETTLEMENT_DATE)
    assert len(figure.data) == 2
    assert figure.layout.barmode == "stack"
