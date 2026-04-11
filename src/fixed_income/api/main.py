"""FastAPI application for the fixed income engine."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from fixed_income.analytics.convexity import convexity
from fixed_income.analytics.duration import macaulay_duration, modified_duration
from fixed_income.analytics.dv01 import dv01
from fixed_income.curves.bootstrapper import Bootstrapper

from .exceptions import configure_exception_handlers
from .schemas import (
    BondPriceRequest,
    BondPriceResponse,
    BondYtmRequest,
    BondYtmResponse,
    CurveBootstrapRequest,
    CurveBootstrapResponse,
    DurationAnalyticsResponse,
    DurationRequest,
    ErrorResponse,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    RiskReportRow,
)
from .services import bad_request, build_bond, build_market_instruments, default_curve_instruments

app = FastAPI(
    title="CurveCraft Fixed Income API",
    version="0.2.0",
    description="Bond pricing, curve bootstrapping, and fixed income risk analytics.",
)
configure_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok", "service": "curvecraft-api"}


@app.post("/bond/price", response_model=BondPriceResponse, responses={400: {"model": ErrorResponse}})
def price_bond(request: BondPriceRequest) -> BondPriceResponse:
    """Price a bond from a yield."""
    bond = build_bond(request)
    settlement_date = request.settlement_date or request.issue_date
    try:
        dirty_price = bond.dirty_price(yield_=request.yield_, settlement_date=settlement_date)
        clean_price = bond.clean_price(yield_=request.yield_, settlement_date=settlement_date)
        accrued_interest = bond.accrued_interest(settlement_date=settlement_date)
    except ValueError as error:
        raise bad_request(str(error)) from error
    return BondPriceResponse(dirty_price=dirty_price, clean_price=clean_price, accrued_interest=accrued_interest)


@app.post("/bond/ytm", response_model=BondYtmResponse, responses={400: {"model": ErrorResponse}})
def bond_ytm(request: BondYtmRequest) -> BondYtmResponse:
    """Solve for bond yield to maturity from dirty price."""
    bond = build_bond(request.bond_spec)
    try:
        ytm = bond.yield_to_maturity(dirty_price=request.dirty_price, settlement_date=request.settlement_date)
    except (ValueError, RuntimeError) as error:
        raise bad_request(str(error)) from error
    return BondYtmResponse(ytm=ytm)


@app.post("/analytics/duration", response_model=DurationAnalyticsResponse, responses={400: {"model": ErrorResponse}})
def duration_analytics(request: DurationRequest) -> DurationAnalyticsResponse:
    """Return yield-based duration, DV01, and convexity analytics."""
    bond = build_bond(request.bond_spec)
    try:
        macaulay = macaulay_duration(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        modified = modified_duration(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        bond_dv01 = dv01(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        bond_convexity = convexity(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
    except ValueError as error:
        raise bad_request(str(error)) from error
    return DurationAnalyticsResponse(
        macaulay=macaulay,
        modified=modified,
        dv01=bond_dv01,
        convexity=bond_convexity,
    )


@app.post("/curve/bootstrap", response_model=CurveBootstrapResponse, responses={400: {"model": ErrorResponse}})
def bootstrap_curve(request: CurveBootstrapRequest) -> CurveBootstrapResponse:
    """Bootstrap a zero curve from market instruments."""
    instruments = build_market_instruments(request.instruments)
    zero_curve = Bootstrapper(instruments).bootstrap()
    return CurveBootstrapResponse(
        tenors=[float(value) for value in zero_curve.maturities.tolist()],
        spot_rates=[float(zero_curve.spot_rate(float(t))) for t in zero_curve.maturities.tolist()],
        discount_factors=[float(value) for value in zero_curve.discount_factors.tolist()],
    )


@app.post("/portfolio/risk", response_model=PortfolioRiskResponse, responses={400: {"model": ErrorResponse}})
def portfolio_risk(request: PortfolioRiskRequest) -> PortfolioRiskResponse:
    """Return aggregate portfolio risk measures and a risk report."""
    try:
        from fixed_income.portfolio.portfolio import Portfolio
    except ImportError as error:
        raise HTTPException(status_code=500, detail="Portfolio module is unavailable.") from error

    portfolio = Portfolio()
    for position in request.positions:
        bond = build_bond(position.bond_spec)
        portfolio.add_position(bond=bond, notional=position.notional, direction=position.direction)

    try:
        curve_source = "request" if request.curve_instruments else "default_sample"
        curve_instruments = (
            build_market_instruments(request.curve_instruments)
            if request.curve_instruments is not None
            else default_curve_instruments()
        )
        zero_curve = Bootstrapper(curve_instruments).bootstrap()
        total_mv = portfolio.total_market_value(zero_curve=zero_curve, settlement_date=request.settlement_date)
        total_dv01 = portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=request.settlement_date)
        weighted_duration = portfolio.portfolio_duration(zero_curve=zero_curve, settlement_date=request.settlement_date)
        risk_report = portfolio.risk_report(zero_curve=zero_curve, settlement_date=request.settlement_date)
    except ValueError as error:
        raise bad_request(str(error)) from error

    report_rows = [RiskReportRow.model_validate(row) for row in risk_report.to_dict(orient="records")]
    return PortfolioRiskResponse(
        total_mv=total_mv,
        total_dv01=total_dv01,
        weighted_duration=weighted_duration,
        curve_source=curve_source,
        risk_report=report_rows,
    )
