"""Dashboard-oriented API helpers for the CurveCraft web interface."""

from __future__ import annotations

import numpy as np

from fixed_income.analytics.convexity import convexity, effective_convexity
from fixed_income.analytics.duration import BASIS_POINT, effective_duration, macaulay_duration, modified_duration, price_from_curve
from fixed_income.analytics.dv01 import dv01, dv01_from_curve
from fixed_income.analytics.key_rate_dv01 import key_rate_dv01
from fixed_income.curves.bootstrapper import Bootstrapper
from fixed_income.curves.zero_curve import ZeroCurve
from fixed_income.portfolio.portfolio import Portfolio

from .schemas import (
    BondCurvePriceRequest,
    BondCurvePriceResponse,
    BondDashboardRequest,
    BondDashboardResponse,
    BondScenarioResponse,
    CashFlowRow,
    CurveBondMetrics,
    CurveDashboardRequest,
    CurveDashboardResponse,
    CurveNodeRow,
    DashboardConfigResponse,
    HedgeAnalysisRequest,
    HedgeAnalysisResponse,
    KeyRateRequest,
    KeyRateResponse,
    PortfolioDashboardRequest,
    PortfolioDashboardResponse,
    PortfolioKeyRateRow,
    RiskReportRow,
)
from .services import build_bond, build_market_instruments, default_curve_instruments

CURVE_FORWARD_STEP = 1.0 / 12.0
STANDARD_SCENARIO_BPS = 10.0
FRONT_END_CUTOFF = 2.0
LONG_END_CUTOFF = 10.0


def build_dashboard_config() -> DashboardConfigResponse:
    """Return sample payloads and supported options for the web dashboard."""
    sample_curve_request = {
        "instruments": [
            {"type": "deposit", "tenor": "1M", "rate": 0.05, "settlement_days": 2},
            {"type": "deposit", "tenor": "3M", "rate": 0.051, "settlement_days": 2},
            {"type": "deposit", "tenor": "6M", "rate": 0.0515, "settlement_days": 2},
            {"type": "deposit", "tenor": "1Y", "rate": 0.052, "settlement_days": 2},
            {"type": "swap", "tenor": "2Y", "rate": 0.0525, "settlement_days": 2},
            {"type": "swap", "tenor": "5Y", "rate": 0.053, "settlement_days": 2},
            {"type": "swap", "tenor": "10Y", "rate": 0.0535, "settlement_days": 2},
            {"type": "swap", "tenor": "30Y", "rate": 0.054, "settlement_days": 2},
        ],
        "max_maturity": 30.0,
        "grid_points": 60,
        "scenario_parallel_shift_bps": 15.0,
    }
    sample_bond_request = {
        "bond_spec": {
            "face": 1000.0,
            "coupon_rate": 0.05,
            "maturity": "2035-01-01",
            "issue_date": "2025-01-01",
            "frequency": 2,
            "day_count": "ACT/ACT",
        },
        "yield": 0.05,
        "settlement_date": "2025-01-01",
        "scenario_bump_bps": 25.0,
        "yield_range_min": 0.01,
        "yield_range_max": 0.12,
        "price_yield_points": 41,
    }
    sample_portfolio_request = {
        "positions": [
            {
                "bond_spec": {
                    "face": 1000.0,
                    "coupon_rate": 0.05,
                    "maturity": "2035-01-01",
                    "issue_date": "2025-01-01",
                    "frequency": 2,
                    "day_count": "ACT/ACT",
                },
                "notional": 2_000_000.0,
                "direction": 1,
            },
            {
                "bond_spec": {
                    "face": 1000.0,
                    "coupon_rate": 0.04,
                    "maturity": "2029-01-01",
                    "issue_date": "2025-01-01",
                    "frequency": 2,
                    "day_count": "ACT/ACT",
                },
                "notional": 1_000_000.0,
                "direction": -1,
            },
        ],
        "settlement_date": "2025-01-01",
        "curve_instruments": sample_curve_request["instruments"],
        "scenario_parallel_shift_bps": 20.0,
    }
    assumptions = [
        "Swap fixed leg bootstrap currently assumes annual fixed payments.",
        "Supported day count conventions: ACT/ACT, 30/360, ACT/360.",
        "Business-day adjustment in coupon schedules uses Modified Following with weekday-only logic.",
    ]
    return DashboardConfigResponse(
        day_count_options=["ACT/ACT", "30/360", "ACT/360"],
        frequency_options=[1, 2, 4],
        sample_bond_request=sample_bond_request,
        sample_curve_request=sample_curve_request,
        sample_portfolio_request=sample_portfolio_request,
        assumptions=assumptions,
    )


def build_bond_dashboard(request: BondDashboardRequest) -> BondDashboardResponse:
    """Return dashboard-ready bond analytics and chart series."""
    bond = build_bond(request.bond_spec)
    settlement_date = request.settlement_date

    dirty_price = bond.dirty_price(yield_=request.yield_, settlement_date=settlement_date)
    clean_price = bond.clean_price(yield_=request.yield_, settlement_date=settlement_date)
    accrued_interest = bond.accrued_interest(settlement_date=settlement_date)
    solved_ytm = bond.yield_to_maturity(dirty_price=dirty_price, settlement_date=settlement_date)
    macaulay = macaulay_duration(bond=bond, yield_=request.yield_, settlement_date=settlement_date)
    modified = modified_duration(bond=bond, yield_=request.yield_, settlement_date=settlement_date)
    bond_dv01 = dv01(bond=bond, yield_=request.yield_, settlement_date=settlement_date)
    bond_convexity = convexity(bond=bond, yield_=request.yield_, settlement_date=settlement_date)

    shock = request.scenario_bump_bps * BASIS_POINT
    clean_price_up = bond.clean_price(yield_=request.yield_ + shock, settlement_date=settlement_date)
    clean_price_down = bond.clean_price(
        yield_=max(request.yield_ - shock, -0.9999),
        settlement_date=settlement_date,
    )

    yield_grid = np.linspace(
        request.yield_range_min,
        request.yield_range_max,
        request.price_yield_points,
    )
    clean_price_grid = [
        float(bond.clean_price(yield_=float(yield_value), settlement_date=settlement_date))
        for yield_value in yield_grid
    ]

    cash_flow_frame = bond.get_cash_flows()
    cash_flow_frame = cash_flow_frame[cash_flow_frame["date"] >= settlement_date]
    cash_flows = [
        CashFlowRow(
            date=row.date,
            coupon=float(row.coupon),
            principal=float(row.principal),
            total_cf=float(row.total_cf),
        )
        for row in cash_flow_frame.itertuples(index=False)
    ]

    return BondDashboardResponse(
        dirty_price=float(dirty_price),
        clean_price=float(clean_price),
        accrued_interest=float(accrued_interest),
        ytm=float(solved_ytm),
        macaulay=float(macaulay),
        modified=float(modified),
        dv01=float(bond_dv01),
        convexity=float(bond_convexity),
        scenario=BondScenarioResponse(
            bump_bps=float(request.scenario_bump_bps),
            clean_price_up=float(clean_price_up),
            clean_price_down=float(clean_price_down),
            delta_up=float(clean_price_up - clean_price),
            delta_down=float(clean_price_down - clean_price),
        ),
        price_yield_yields=[float(value) for value in yield_grid.tolist()],
        price_yield_clean_prices=clean_price_grid,
        cash_flows=cash_flows,
    )


def build_bond_curve_price(request: BondCurvePriceRequest) -> BondCurvePriceResponse:
    """Return curve-based pricing metrics for one or two bonds."""
    instruments = build_market_instruments(request.curve_instruments)
    zero_curve = Bootstrapper(instruments).bootstrap()

    primary_bond = build_bond(request.bond_spec)
    metrics = [_curve_bond_metrics("Bond A", primary_bond, zero_curve, request.settlement_date)]
    if request.compare_bond_spec is not None:
        compare_bond = build_bond(request.compare_bond_spec)
        metrics.append(_curve_bond_metrics(request.compare_label, compare_bond, zero_curve, request.settlement_date))
    return BondCurvePriceResponse(curve_source="request", metrics=metrics)


def build_curve_dashboard(request: CurveDashboardRequest) -> CurveDashboardResponse:
    """Return dashboard-ready zero-curve analytics and sampled curve views."""
    instruments = build_market_instruments(request.instruments)
    zero_curve = Bootstrapper(instruments).bootstrap()
    curve_grid = np.linspace(CURVE_FORWARD_STEP, request.max_maturity, request.grid_points)
    par_maturities = np.arange(1.0, float(int(request.max_maturity)) + 1.0, 1.0)

    shifted_curve = zero_curve.bumped_parallel(request.scenario_parallel_shift_bps * BASIS_POINT)
    scenario_curves = _scenario_curves(zero_curve)

    return CurveDashboardResponse(
        nodes=[
            CurveNodeRow(
                tenor_years=float(maturity),
                discount_factor=float(discount_factor),
                spot_rate=float(zero_curve.spot_rate(float(maturity))),
            )
            for maturity, discount_factor in zip(
                zero_curve.maturities,
                zero_curve.discount_factors,
                strict=True,
            )
        ],
        curve_maturities=[float(value) for value in curve_grid.tolist()],
        spot_rates=[float(zero_curve.spot_rate(float(t))) for t in curve_grid],
        forward_rates=[
            float(zero_curve.forward_rate(max(float(t) - CURVE_FORWARD_STEP, 1e-6), float(t)))
            for t in curve_grid
        ],
        par_maturities=[float(value) for value in par_maturities.tolist()],
        par_rates=[float(zero_curve.par_rate(float(t))) for t in par_maturities],
        scenario_parallel_shift_bps=float(request.scenario_parallel_shift_bps),
        shifted_spot_rates=[float(shifted_curve.spot_rate(float(t))) for t in curve_grid],
        scenario_rates={
            name: [float(curve.spot_rate(float(t))) for t in curve_grid]
            for name, curve in scenario_curves.items()
        },
    )


def build_key_rate_response(request: KeyRateRequest) -> KeyRateResponse:
    """Return dedicated key-rate DV01 outputs for a single bond."""
    bond = build_bond(request.bond_spec)
    zero_curve = Bootstrapper(build_market_instruments(request.curve_instruments)).bootstrap()
    key_rate_map, key_rate_series = key_rate_dv01(
        bond=bond,
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
        bump_bps=request.bump_bps,
    )
    total_curve_dv01 = dv01_from_curve(
        bond=bond,
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
    )
    return KeyRateResponse(
        bump_bps=float(request.bump_bps),
        key_rate_dv01={f"{tenor:g}Y": float(value) for tenor, value in key_rate_map.items()},
        total_key_rate_dv01=float(key_rate_series.sum()),
        total_curve_dv01=float(total_curve_dv01),
    )


def build_portfolio_dashboard(request: PortfolioDashboardRequest) -> PortfolioDashboardResponse:
    """Return dashboard-ready portfolio analytics and scenario results."""
    portfolio = Portfolio()
    for position in request.positions:
        bond = build_bond(position.bond_spec)
        portfolio.add_position(bond=bond, notional=position.notional, direction=position.direction)

    curve_source = "request" if request.curve_instruments else "default_sample"
    curve_instruments = (
        build_market_instruments(request.curve_instruments)
        if request.curve_instruments is not None
        else default_curve_instruments()
    )
    zero_curve = Bootstrapper(curve_instruments).bootstrap()

    total_mv = portfolio.total_market_value(zero_curve=zero_curve, settlement_date=request.settlement_date)
    total_dv01 = portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=request.settlement_date)
    weighted_duration = portfolio.portfolio_duration(
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
    )
    risk_report = portfolio.risk_report(zero_curve=zero_curve, settlement_date=request.settlement_date)
    key_rate_profile = portfolio.key_rate_dv01_profile(
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
    )

    shifted_curve = zero_curve.bumped_parallel(request.scenario_parallel_shift_bps * BASIS_POINT)
    shifted_total_mv = portfolio.total_market_value(
        zero_curve=shifted_curve,
        settlement_date=request.settlement_date,
    )
    scenario_results = {}
    for name, scenario_curve in _scenario_curves(zero_curve).items():
        scenario_results[name] = float(
            portfolio.total_market_value(zero_curve=scenario_curve, settlement_date=request.settlement_date) - total_mv
        )

    return PortfolioDashboardResponse(
        total_mv=float(total_mv),
        total_dv01=float(total_dv01),
        weighted_duration=float(weighted_duration),
        curve_source=curve_source,
        risk_report=[RiskReportRow.model_validate(row) for row in risk_report.to_dict(orient="records")],
        key_rate_profile=_portfolio_key_rate_rows(key_rate_profile=key_rate_profile),
        scenario_parallel_shift_bps=float(request.scenario_parallel_shift_bps),
        shifted_total_mv=float(shifted_total_mv),
        scenario_pnl=float(shifted_total_mv - total_mv),
        scenario_results=scenario_results,
    )


def build_hedge_analysis(request: HedgeAnalysisRequest) -> HedgeAnalysisResponse:
    """Return required hedge notional to move portfolio DV01 to a target."""
    portfolio = Portfolio()
    for position in request.positions:
        portfolio.add_position(
            bond=build_bond(position.bond_spec),
            notional=position.notional,
            direction=position.direction,
        )
    hedge_bond = build_bond(request.hedge_bond_spec)
    curve_instruments = (
        build_market_instruments(request.curve_instruments)
        if request.curve_instruments is not None
        else default_curve_instruments()
    )
    zero_curve = Bootstrapper(curve_instruments).bootstrap()
    current_dv01 = portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=request.settlement_date)
    required_hedge_notional = portfolio.hedge_trade(
        target_dv01=request.target_dv01,
        hedge_bond=hedge_bond,
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
    )
    hedge_unit_dv01 = dv01_from_curve(
        bond=hedge_bond,
        zero_curve=zero_curve,
        settlement_date=request.settlement_date,
    ) / hedge_bond.face_value
    projected_post_hedge_dv01 = current_dv01 + required_hedge_notional * hedge_unit_dv01
    return HedgeAnalysisResponse(
        current_portfolio_dv01=float(current_dv01),
        target_dv01=float(request.target_dv01),
        required_hedge_notional=float(required_hedge_notional),
        hedge_bond_unit_dv01=float(hedge_unit_dv01),
        projected_post_hedge_dv01=float(projected_post_hedge_dv01),
    )


def _curve_bond_metrics(label: str, bond, zero_curve: ZeroCurve, settlement_date) -> CurveBondMetrics:
    """Return curve-based metrics for a single bond."""
    dirty_price = price_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    clean_price = dirty_price - bond.accrued_interest(settlement_date=settlement_date)
    curve_dv01 = dv01_from_curve(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    eff_duration = effective_duration(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    eff_convexity = effective_convexity(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    key_rate_map, _ = key_rate_dv01(bond=bond, zero_curve=zero_curve, settlement_date=settlement_date)
    return CurveBondMetrics(
        label=label,
        dirty_price_from_curve=float(dirty_price),
        clean_price_from_curve=float(clean_price),
        effective_duration=float(eff_duration),
        effective_convexity=float(eff_convexity),
        dv01_from_curve=float(curve_dv01),
        key_rate_dv01={f"{tenor:g}Y": float(value) for tenor, value in key_rate_map.items()},
    )


def _portfolio_key_rate_rows(key_rate_profile) -> list[PortfolioKeyRateRow]:
    """Convert the key-rate profile DataFrame into API rows."""
    rows: list[PortfolioKeyRateRow] = []
    for record in key_rate_profile.to_dict(orient="records"):
        name = str(record["name"])
        buckets = {column: float(value) for column, value in record.items() if column != "name"}
        rows.append(PortfolioKeyRateRow(name=name, buckets=buckets))
    return rows


def _scenario_curves(zero_curve: ZeroCurve) -> dict[str, ZeroCurve]:
    """Return standard stress scenarios used across curve and portfolio dashboards."""
    return {
        "parallel_up_10bps": zero_curve.bumped_parallel(STANDARD_SCENARIO_BPS * BASIS_POINT),
        "parallel_down_10bps": zero_curve.bumped_parallel(-STANDARD_SCENARIO_BPS * BASIS_POINT),
        "steepener_2s10s": _apply_piecewise_spot_shift(
            zero_curve=zero_curve,
            front_shift_bps=-STANDARD_SCENARIO_BPS,
            back_shift_bps=STANDARD_SCENARIO_BPS,
            front_cutoff=2.0,
            back_cutoff=10.0,
        ),
        "front_end_up_10bps": _apply_bucket_spot_shift(
            zero_curve=zero_curve,
            cutoff=FRONT_END_CUTOFF,
            shift_bps=STANDARD_SCENARIO_BPS,
            direction="front",
        ),
        "long_end_up_10bps": _apply_bucket_spot_shift(
            zero_curve=zero_curve,
            cutoff=LONG_END_CUTOFF,
            shift_bps=STANDARD_SCENARIO_BPS,
            direction="long",
        ),
    }


def _apply_bucket_spot_shift(zero_curve: ZeroCurve, cutoff: float, shift_bps: float, direction: str) -> ZeroCurve:
    """Apply a simple bucketed spot-rate shift to front-end or long-end nodes."""
    spot_rates = np.array(
        [0.0 if np.isclose(t, 0.0) else zero_curve.spot_rate(float(t)) for t in zero_curve.maturities],
        dtype=float,
    )
    shift = shift_bps * BASIS_POINT
    for index, maturity in enumerate(zero_curve.maturities):
        if np.isclose(maturity, 0.0):
            continue
        if direction == "front" and maturity <= cutoff:
            spot_rates[index] += shift
        if direction == "long" and maturity >= cutoff:
            spot_rates[index] += shift
    discount_factors = np.exp(-spot_rates * zero_curve.maturities)
    discount_factors[0] = 1.0
    return ZeroCurve(
        maturities=zero_curve.maturities.copy(),
        discount_factors=discount_factors,
        interpolation_method=zero_curve.interpolation_method,
    )


def _apply_piecewise_spot_shift(
    zero_curve: ZeroCurve,
    front_shift_bps: float,
    back_shift_bps: float,
    front_cutoff: float,
    back_cutoff: float,
) -> ZeroCurve:
    """Apply a piecewise-linear 2s10s-style steepener shift on spot rates."""
    spot_rates = np.array(
        [0.0 if np.isclose(t, 0.0) else zero_curve.spot_rate(float(t)) for t in zero_curve.maturities],
        dtype=float,
    )
    for index, maturity in enumerate(zero_curve.maturities):
        if np.isclose(maturity, 0.0):
            continue
        if maturity <= front_cutoff:
            shift_bps = front_shift_bps
        elif maturity >= back_cutoff:
            shift_bps = back_shift_bps
        else:
            weight = (maturity - front_cutoff) / (back_cutoff - front_cutoff)
            shift_bps = (1.0 - weight) * front_shift_bps + weight * back_shift_bps
        spot_rates[index] += shift_bps * BASIS_POINT
    discount_factors = np.exp(-spot_rates * zero_curve.maturities)
    discount_factors[0] = 1.0
    return ZeroCurve(
        maturities=zero_curve.maturities.copy(),
        discount_factors=discount_factors,
        interpolation_method=zero_curve.interpolation_method,
    )
