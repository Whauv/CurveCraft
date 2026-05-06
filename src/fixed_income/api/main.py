"""FastAPI application for the fixed income engine."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from fixed_income.analytics.convexity import convexity
from fixed_income.analytics.duration import macaulay_duration, modified_duration
from fixed_income.analytics.dv01 import dv01
from fixed_income.curves.bootstrapper import Bootstrapper

from .dashboard import (
    build_bond_curve_price,
    build_bond_dashboard,
    build_curve_dashboard,
    build_dashboard_config,
    build_hedge_analysis,
    build_key_rate_response,
    build_portfolio_dashboard,
)
from .exceptions import configure_exception_handlers
from .schemas import (
    BondDashboardRequest,
    BondDashboardResponse,
    BondCurvePriceRequest,
    BondCurvePriceResponse,
    BondPriceRequest,
    BondPriceResponse,
    BondYtmRequest,
    BondYtmResponse,
    CurveBootstrapRequest,
    CurveBootstrapResponse,
    CurveDashboardRequest,
    CurveDashboardResponse,
    DashboardConfigResponse,
    DurationAnalyticsResponse,
    DurationRequest,
    ErrorResponse,
    HedgeAnalysisRequest,
    HedgeAnalysisResponse,
    KeyRateRequest,
    KeyRateResponse,
    PortfolioDashboardRequest,
    PortfolioDashboardResponse,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    RiskReportRow,
)
from .services import bad_request, build_bond, build_market_instruments, default_curve_instruments

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_PATH = STATIC_DIR / "index.html"
INDEX_TEMPLATE = INDEX_PATH.read_text(encoding="utf-8")

app = FastAPI(
    title="CurveCraft Fixed Income API",
    version="0.2.0",
    description="Bond pricing, curve bootstrapping, and fixed income risk analytics.",
)
configure_exception_handlers(app)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard_home(request: Request) -> HTMLResponse:
    """Serve the dashboard homepage."""
    page = (request.query_params.get("page") or "bond").strip().lower()
    if page == "curve":
        return _render_dashboard_page("curve-workspace")
    if page == "portfolio":
        return _render_dashboard_page("portfolio-workspace")
    return _render_dashboard_page("bond-workspace")


@app.get("/bond", include_in_schema=False)
@app.get("/bond/", include_in_schema=False)
def dashboard_bond_page() -> HTMLResponse:
    """Serve the dedicated bond analytics page."""
    return _render_dashboard_page("bond-workspace")


@app.get("/curve", include_in_schema=False)
@app.get("/curve/", include_in_schema=False)
def dashboard_curve_page() -> HTMLResponse:
    """Serve the dedicated curve analytics page."""
    return _render_dashboard_page("curve-workspace")


@app.get("/portfolio", include_in_schema=False)
@app.get("/portfolio/", include_in_schema=False)
def dashboard_portfolio_page() -> HTMLResponse:
    """Serve the dedicated portfolio analytics page."""
    return _render_dashboard_page("portfolio-workspace")


def _render_dashboard_page(initial_workspace: str) -> HTMLResponse:
    """Render dashboard HTML with a route-specific initial workspace."""
    html = INDEX_TEMPLATE
    workspaces = ("bond-workspace", "curve-workspace", "portfolio-workspace")
    for workspace in workspaces:
        active_class = "workspace is-active" if workspace == initial_workspace else "workspace"
        html = html.replace(
            f'<section class="workspace is-active" id="{workspace}">',
            f'<section class="{active_class}" id="{workspace}">',
        )
        html = html.replace(
            f'<section class="workspace" id="{workspace}">',
            f'<section class="{active_class}" id="{workspace}">',
        )
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok", "service": "curvecraft-api"}


@app.get("/dashboard/config", response_model=DashboardConfigResponse)
def dashboard_config() -> DashboardConfigResponse:
    """Return supported options and sample payloads for the web dashboard."""
    return build_dashboard_config()


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


@app.post("/dashboard/bond", response_model=BondDashboardResponse, responses={400: {"model": ErrorResponse}})
def bond_dashboard(request: BondDashboardRequest) -> BondDashboardResponse:
    """Return dashboard-ready bond analytics and chart data."""
    try:
        return build_bond_dashboard(request)
    except (ValueError, RuntimeError) as error:
        raise bad_request(str(error)) from error


@app.post(
    "/dashboard/bond-curve-price",
    response_model=BondCurvePriceResponse,
    responses={400: {"model": ErrorResponse}},
)
def bond_curve_price_dashboard(request: BondCurvePriceRequest) -> BondCurvePriceResponse:
    """Return curve-based bond pricing metrics and optional compare mode results."""
    try:
        return build_bond_curve_price(request)
    except (ValueError, RuntimeError) as error:
        raise bad_request(str(error)) from error


@app.post("/dashboard/curve", response_model=CurveDashboardResponse, responses={400: {"model": ErrorResponse}})
def curve_dashboard(request: CurveDashboardRequest) -> CurveDashboardResponse:
    """Return dashboard-ready curve analytics and scenario overlays."""
    try:
        return build_curve_dashboard(request)
    except ValueError as error:
        raise bad_request(str(error)) from error


@app.post("/dashboard/key-rate", response_model=KeyRateResponse, responses={400: {"model": ErrorResponse}})
def key_rate_dashboard(request: KeyRateRequest) -> KeyRateResponse:
    """Return dedicated key-rate DV01 analytics for a single bond."""
    try:
        return build_key_rate_response(request)
    except ValueError as error:
        raise bad_request(str(error)) from error


@app.post(
    "/dashboard/portfolio",
    response_model=PortfolioDashboardResponse,
    responses={400: {"model": ErrorResponse}},
)
def portfolio_dashboard(request: PortfolioDashboardRequest) -> PortfolioDashboardResponse:
    """Return dashboard-ready portfolio analytics and scenario outputs."""
    try:
        return build_portfolio_dashboard(request)
    except ValueError as error:
        raise bad_request(str(error)) from error


@app.post("/dashboard/hedge", response_model=HedgeAnalysisResponse, responses={400: {"model": ErrorResponse}})
def hedge_dashboard(request: HedgeAnalysisRequest) -> HedgeAnalysisResponse:
    """Return hedge notional required to move portfolio DV01 to target."""
    try:
        return build_hedge_analysis(request)
    except ValueError as error:
        raise bad_request(str(error)) from error
