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
