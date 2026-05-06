"""Pydantic schemas for the fixed income API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SUPPORTED_DAY_COUNT = {"ACT/ACT", "30/360", "ACT/360"}
SUPPORTED_FREQUENCIES = {1, 2, 4}


class BondSpec(BaseModel):
    """Bond specification for API requests."""

    face: float = Field(..., gt=0.0)
    coupon_rate: float = Field(..., ge=0.0)
    maturity: date
    issue_date: date
    frequency: int
    day_count: str

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: int) -> int:
        """Validate coupon frequency."""
        if value not in SUPPORTED_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(SUPPORTED_FREQUENCIES)}")
        return value

    @field_validator("day_count")
    @classmethod
    def validate_day_count(cls, value: str) -> str:
        """Validate day-count convention."""
        if value not in SUPPORTED_DAY_COUNT:
            raise ValueError(f"day_count must be one of {sorted(SUPPORTED_DAY_COUNT)}")
        return value

    @field_validator("maturity")
    @classmethod
    def validate_maturity(cls, value: date, info) -> date:
        """Validate maturity ordering."""
        issue_date = info.data.get("issue_date")
        if issue_date is not None and value <= issue_date:
            raise ValueError("maturity must be later than issue_date")
        return value


class BondPriceRequest(BondSpec):
    """Request body for `/bond/price`."""

    yield_: float = Field(..., alias="yield", gt=-1.0)
    settlement_date: date | None = None


class BondYtmRequest(BaseModel):
    """Request body for `/bond/ytm`."""

    bond_spec: BondSpec
    dirty_price: float = Field(..., gt=0.0)
    settlement_date: date


class DurationRequest(BaseModel):
    """Request body for `/analytics/duration`."""

    bond_spec: BondSpec
    yield_: float = Field(..., alias="yield", gt=-1.0)
    settlement_date: date


class CurveInstrumentRequest(BaseModel):
    """Single market instrument request item."""

    type: Literal["deposit", "fra", "swap"]
    tenor: str
    rate: float = Field(..., gt=-1.0)
    settlement_days: int = Field(default=2, ge=0)


class CurveBootstrapRequest(BaseModel):
    """Request body for `/curve/bootstrap`."""

    instruments: list[CurveInstrumentRequest]

    @field_validator("instruments")
    @classmethod
    def validate_instruments(cls, value: list[CurveInstrumentRequest]) -> list[CurveInstrumentRequest]:
        """Ensure at least one market instrument is supplied."""
        if not value:
            raise ValueError("instruments must not be empty")
        return value


class PortfolioPositionRequest(BaseModel):
    """Single portfolio position request item."""

    bond_spec: BondSpec
    notional: float = Field(..., gt=0.0)
    direction: Literal[-1, 1]


class PortfolioRiskRequest(BaseModel):
    """Request body for `/portfolio/risk`."""

    positions: list[PortfolioPositionRequest]
    settlement_date: date
    curve_instruments: list[CurveInstrumentRequest] | None = None

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, value: list[PortfolioPositionRequest]) -> list[PortfolioPositionRequest]:
        """Ensure at least one position is supplied."""
        if not value:
            raise ValueError("positions must not be empty")
        return value


class ErrorResponse(BaseModel):
    """Structured error response."""

    detail: str
    request_id: str | None = None


class BondPriceResponse(BaseModel):
    """Bond pricing response payload."""

    dirty_price: float
    clean_price: float
    accrued_interest: float


class BondYtmResponse(BaseModel):
    """Bond YTM response payload."""

    ytm: float


class DurationAnalyticsResponse(BaseModel):
    """Duration analytics response payload."""

    macaulay: float
    modified: float
    dv01: float
    convexity: float


class CurveBootstrapResponse(BaseModel):
    """Curve bootstrap response payload."""

    tenors: list[float]
    spot_rates: list[float]
    discount_factors: list[float]


class RiskReportRow(BaseModel):
    """Single row in a portfolio risk report."""

    cusip_name: str = Field(alias="CUSIP/name")
    notional: float
    mv: float = Field(alias="MV")
    dv01: float = Field(alias="DV01")
    duration: float
    convexity: float


class PortfolioRiskResponse(BaseModel):
    """Portfolio risk response payload."""

    total_mv: float
    total_dv01: float
    weighted_duration: float
    curve_source: str
    risk_report: list[RiskReportRow]


class BondDashboardRequest(BaseModel):
    """Request body for the bond dashboard workflow."""

    bond_spec: BondSpec
    yield_: float = Field(..., alias="yield", gt=-1.0)
    settlement_date: date
    scenario_bump_bps: float = Field(default=25.0, ge=0.0, le=500.0)
    yield_range_min: float = Field(default=0.01, gt=-1.0, lt=1.0)
    yield_range_max: float = Field(default=0.15, gt=-1.0, lt=2.0)
    price_yield_points: int = Field(default=31, ge=5, le=200)

    @field_validator("yield_range_max")
    @classmethod
    def validate_yield_range_max(cls, value: float, info) -> float:
        """Ensure the upper yield-range bound exceeds the lower bound."""
        lower_bound = info.data.get("yield_range_min")
        if lower_bound is not None and value <= lower_bound:
            raise ValueError("yield_range_max must be greater than yield_range_min")
        return value


class BondScenarioResponse(BaseModel):
    """Scenario pricing response for the bond dashboard."""

    bump_bps: float
    clean_price_up: float
    clean_price_down: float
    delta_up: float
    delta_down: float


class CashFlowRow(BaseModel):
    """Single dashboard cash-flow row."""

    date: date
    coupon: float
    principal: float
    total_cf: float


class BondDashboardResponse(BaseModel):
    """Response payload for the bond dashboard workflow."""

    dirty_price: float
    clean_price: float
    accrued_interest: float
    ytm: float
    macaulay: float
    modified: float
    dv01: float
    convexity: float
    scenario: BondScenarioResponse
    price_yield_yields: list[float]
    price_yield_clean_prices: list[float]
    cash_flows: list[CashFlowRow]


class BondCurvePriceRequest(BaseModel):
    """Request body for curve-based bond pricing and compare mode."""

    bond_spec: BondSpec
    settlement_date: date
    curve_instruments: list[CurveInstrumentRequest]
    compare_bond_spec: BondSpec | None = None
    compare_label: str = Field(default="Bond B", min_length=1, max_length=64)

    @field_validator("curve_instruments")
    @classmethod
    def validate_curve_instruments(
        cls,
        value: list[CurveInstrumentRequest],
    ) -> list[CurveInstrumentRequest]:
        """Ensure at least one instrument is provided for curve pricing."""
        if not value:
            raise ValueError("curve_instruments must not be empty")
        return value


class CurveBondMetrics(BaseModel):
    """Curve-based pricing and risk metrics for a bond."""

    label: str
    dirty_price_from_curve: float
    clean_price_from_curve: float
    effective_duration: float
    effective_convexity: float
    dv01_from_curve: float
    key_rate_dv01: dict[str, float]


class BondCurvePriceResponse(BaseModel):
    """Response payload for curve-based bond pricing and compare mode."""

    curve_source: str
    metrics: list[CurveBondMetrics]


class CurveDashboardRequest(BaseModel):
    """Request body for the curve dashboard workflow."""

    instruments: list[CurveInstrumentRequest]
    max_maturity: float = Field(default=30.0, gt=0.5, le=60.0)
    grid_points: int = Field(default=60, ge=12, le=360)
    scenario_parallel_shift_bps: float = Field(default=0.0, ge=-500.0, le=500.0)

    @field_validator("instruments")
    @classmethod
    def validate_curve_dashboard_instruments(
        cls,
        value: list[CurveInstrumentRequest],
    ) -> list[CurveInstrumentRequest]:
        """Ensure the curve dashboard receives at least one instrument."""
        if not value:
            raise ValueError("instruments must not be empty")
        return value


class CurveNodeRow(BaseModel):
    """Single bootstrapped curve node row."""

    tenor_years: float
    discount_factor: float
    spot_rate: float


class CurveDashboardResponse(BaseModel):
    """Response payload for the curve dashboard workflow."""

    nodes: list[CurveNodeRow]
    curve_maturities: list[float]
    spot_rates: list[float]
    forward_rates: list[float]
    par_maturities: list[float]
    par_rates: list[float]
    scenario_parallel_shift_bps: float
    shifted_spot_rates: list[float]
    scenario_rates: dict[str, list[float]]


class PortfolioKeyRateRow(BaseModel):
    """Single row in the portfolio key-rate DV01 profile."""

    name: str
    buckets: dict[str, float]


class PortfolioDashboardRequest(BaseModel):
    """Request body for the portfolio dashboard workflow."""

    positions: list[PortfolioPositionRequest]
    settlement_date: date
    curve_instruments: list[CurveInstrumentRequest] | None = None
    scenario_parallel_shift_bps: float = Field(default=25.0, ge=-500.0, le=500.0)

    @field_validator("positions")
    @classmethod
    def validate_dashboard_positions(
        cls,
        value: list[PortfolioPositionRequest],
    ) -> list[PortfolioPositionRequest]:
        """Ensure the portfolio dashboard receives at least one position."""
        if not value:
            raise ValueError("positions must not be empty")
        return value


class PortfolioDashboardResponse(BaseModel):
    """Response payload for the portfolio dashboard workflow."""

    total_mv: float
    total_dv01: float
    weighted_duration: float
    curve_source: str
    risk_report: list[RiskReportRow]
    key_rate_profile: list[PortfolioKeyRateRow]
    scenario_parallel_shift_bps: float
    shifted_total_mv: float
    scenario_pnl: float
    scenario_results: dict[str, float]


class KeyRateRequest(BaseModel):
    """Request body for dedicated key-rate DV01 analysis."""

    bond_spec: BondSpec
    settlement_date: date
    curve_instruments: list[CurveInstrumentRequest]
    bump_bps: float = Field(default=1.0, ge=0.1, le=50.0)

    @field_validator("curve_instruments")
    @classmethod
    def validate_key_rate_curve_instruments(
        cls,
        value: list[CurveInstrumentRequest],
    ) -> list[CurveInstrumentRequest]:
        """Ensure at least one instrument is provided."""
        if not value:
            raise ValueError("curve_instruments must not be empty")
        return value


class KeyRateResponse(BaseModel):
    """Response payload for key-rate DV01 analysis."""

    bump_bps: float
    key_rate_dv01: dict[str, float]
    total_key_rate_dv01: float
    total_curve_dv01: float


class HedgeAnalysisRequest(BaseModel):
    """Request body for portfolio DV01 hedge sizing."""

    positions: list[PortfolioPositionRequest]
    settlement_date: date
    hedge_bond_spec: BondSpec
    target_dv01: float = 0.0
    curve_instruments: list[CurveInstrumentRequest] | None = None

    @field_validator("positions")
    @classmethod
    def validate_hedge_positions(
        cls,
        value: list[PortfolioPositionRequest],
    ) -> list[PortfolioPositionRequest]:
        """Ensure at least one position is supplied."""
        if not value:
            raise ValueError("positions must not be empty")
        return value


class HedgeAnalysisResponse(BaseModel):
    """Response payload for hedge analysis."""

    current_portfolio_dv01: float
    target_dv01: float
    required_hedge_notional: float
    hedge_bond_unit_dv01: float
    projected_post_hedge_dv01: float


class DashboardConfigResponse(BaseModel):
    """Sample data and option payload for the dashboard frontend."""

    day_count_options: list[str]
    frequency_options: list[int]
    sample_bond_request: dict[str, object]
    sample_curve_request: dict[str, object]
    sample_portfolio_request: dict[str, object]
    assumptions: list[str]
