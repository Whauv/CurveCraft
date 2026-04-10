"""Plotly visualizations for fixed income analytics."""

from __future__ import annotations

from datetime import date

import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from fixed_income.analytics.duration import modified_duration
from fixed_income.analytics.key_rate_dv01 import STANDARD_TENOR_BUCKETS
from fixed_income.bonds.bond import Bond
from fixed_income.curves.zero_curve import ZeroCurve
from fixed_income.portfolio.portfolio import Portfolio

CURVE_GRID_POINTS = 300
PRICE_YIELD_GRID_POINTS = 120
FORWARD_STEP = 1.0 / 12.0


def plot_yield_curve(zero_curve: ZeroCurve, max_maturity: float = 30.0) -> go.Figure:
    """Plot spot, forward, and par rates on one chart.

    Parameters
    ----------
    zero_curve : ZeroCurve
        Zero curve to visualize.
    max_maturity : float, optional
        Maximum maturity in years shown on the x-axis.

    Returns
    -------
    go.Figure
        Plotly figure containing the yield-curve views.
    """
    maturities = np.linspace(FORWARD_STEP, max_maturity, CURVE_GRID_POINTS)
    spot_rates = [100.0 * zero_curve.spot_rate(float(t)) for t in maturities]
    forward_rates = [100.0 * zero_curve.forward_rate(max(float(t) - FORWARD_STEP, 1e-6), float(t)) for t in maturities]
    par_maturities = np.arange(1.0, float(int(max_maturity)) + 1.0, 1.0)
    par_rates = [100.0 * zero_curve.par_rate(float(t)) for t in par_maturities]

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=maturities, y=spot_rates, mode="lines", name="Spot Rate"))
    figure.add_trace(go.Scatter(x=maturities, y=forward_rates, mode="lines", name="Forward Rate"))
    figure.add_trace(go.Scatter(x=par_maturities, y=par_rates, mode="lines", name="Par Rate"))
    figure.update_layout(
        title="Yield Curve Views",
        xaxis_title="Maturity (Years)",
        yaxis_title="Rate (%)",
        template="plotly_white",
        legend_title="Curve",
    )
    return figure


def plot_price_yield(
    bond: Bond,
    yield_range: tuple[float, float] = (0.01, 0.15),
    settlement_date: date | None = None,
) -> go.Figure:
    """Plot the bond clean price against yield, including a duration tangent.

    Parameters
    ----------
    bond : Bond
        Bond to visualize.
    yield_range : tuple[float, float], optional
        Lower and upper yield bounds.
    settlement_date : date | None, optional
        Valuation or settlement date. Defaults to the bond issue date.

    Returns
    -------
    go.Figure
        Plotly figure of the price-yield relationship.
    """
    settlement = settlement_date or bond.issue_date
    yields = np.linspace(yield_range[0], yield_range[1], PRICE_YIELD_GRID_POINTS)
    clean_prices = np.array([bond.clean_price(yield_=float(y), settlement_date=settlement) for y in yields], dtype=float)

    current_yield = float(np.clip(bond.coupon_rate if bond.coupon_rate > 0.0 else np.mean(yield_range), *yield_range))
    current_price = bond.clean_price(yield_=current_yield, settlement_date=settlement)
    duration_slope = -modified_duration(bond=bond, yield_=current_yield, settlement_date=settlement) * current_price
    tangent_prices = current_price + duration_slope * (yields - current_yield)

    convexity_check_yield = float(min(current_yield + 0.01, yield_range[1]))
    actual_price = bond.clean_price(yield_=convexity_check_yield, settlement_date=settlement)
    tangent_price = current_price + duration_slope * (convexity_check_yield - current_yield)
    convexity_gap = actual_price - tangent_price

    figure = go.Figure()
    figure.add_trace(go.Scatter(x=100.0 * yields, y=clean_prices, mode="lines", name="Clean Price"))
    figure.add_trace(
        go.Scatter(
            x=100.0 * yields,
            y=tangent_prices,
            mode="lines",
            name="Duration Tangent",
            line={"dash": "dash"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[100.0 * current_yield],
            y=[current_price],
            mode="markers",
            name="Current Yield",
            marker={"size": 10},
        )
    )
    figure.add_annotation(
        x=100.0 * convexity_check_yield,
        y=actual_price,
        text=f"Convexity benefit: {convexity_gap:.2f}",
        showarrow=True,
        arrowhead=2,
    )
    figure.update_layout(
        title="Price-Yield Relationship",
        xaxis_title="Yield (%)",
        yaxis_title="Clean Price",
        template="plotly_white",
    )
    return figure


def plot_key_rate_dv01(key_rate_dv01_series) -> go.Figure:
    """Plot key-rate DV01 as a color-scaled bar chart.

    Parameters
    ----------
    key_rate_dv01_series : pd.Series
        Key-rate DV01 values indexed by tenor.

    Returns
    -------
    go.Figure
        Plotly bar chart.
    """
    values = np.asarray(key_rate_dv01_series.values, dtype=float)
    max_abs_value = max(np.max(np.abs(values)), 1e-12)
    normalized = np.abs(values) / max_abs_value
    colors = sample_colorscale("Viridis", normalized)

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=[f"{float(tenor):g}Y" for tenor in key_rate_dv01_series.index],
            y=values,
            marker={"color": colors},
            name="Key Rate DV01",
        )
    )
    figure.update_layout(
        title="Key Rate DV01 Profile",
        xaxis_title="Tenor Bucket",
        yaxis_title="DV01",
        template="plotly_white",
    )
    return figure


def plot_cash_flows(bond: Bond, settlement_date: date | None = None) -> go.Figure:
    """Plot bond cash flows as stacked coupon and principal bars.

    Parameters
    ----------
    bond : Bond
        Bond to visualize.
    settlement_date : date | None, optional
        Settlement date used to filter out historical cash flows. Defaults to the issue date.

    Returns
    -------
    go.Figure
        Plotly stacked bar chart.
    """
    settlement = settlement_date or bond.issue_date
    cash_flows = bond.get_cash_flows()
    cash_flows = cash_flows[cash_flows["date"] >= settlement]

    figure = go.Figure()
    figure.add_trace(go.Bar(x=cash_flows["date"], y=cash_flows["coupon"], name="Coupon"))
    figure.add_trace(go.Bar(x=cash_flows["date"], y=cash_flows["principal"], name="Principal"))
    figure.update_layout(
        title="Bond Cash Flows",
        xaxis_title="Payment Date",
        yaxis_title="Cash Flow",
        barmode="stack",
        template="plotly_white",
    )
    return figure


def plot_portfolio_risk(portfolio: Portfolio, zero_curve: ZeroCurve, settlement_date: date) -> go.Figure:
    """Plot each bond's key-rate DV01 contribution by tenor bucket.

    Parameters
    ----------
    portfolio : Portfolio
        Portfolio to visualize.
    zero_curve : ZeroCurve
        Zero curve used for risk measurement.
    settlement_date : date
        Valuation or settlement date.

    Returns
    -------
    go.Figure
        Plotly stacked bar chart.
    """
    profile = portfolio.key_rate_dv01_profile(zero_curve=zero_curve, settlement_date=settlement_date)
    tenor_columns = [f"{tenor:g}Y" for tenor in STANDARD_TENOR_BUCKETS]
    position_profile = profile[profile["name"] != "Total"]

    figure = go.Figure()
    for _, row in position_profile.iterrows():
        figure.add_trace(
            go.Bar(
                x=tenor_columns,
                y=[float(row[column]) for column in tenor_columns],
                name=str(row["name"]),
            )
        )
    figure.update_layout(
        title="Portfolio Key Rate DV01 Contributions",
        xaxis_title="Tenor Bucket",
        yaxis_title="DV01 Contribution",
        barmode="stack",
        template="plotly_white",
    )
    return figure
