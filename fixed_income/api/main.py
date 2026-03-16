"""FastAPI application for the fixed income engine."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from fixed_income.analytics.convexity import convexity
from fixed_income.analytics.duration import macaulay_duration, modified_duration
from fixed_income.analytics.dv01 import dv01
from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import Bootstrapper, MarketInstrument

SUPPORTED_DAY_COUNT = {"ACT/ACT", "30/360", "ACT/360"}
SUPPORTED_FREQUENCIES = {1, 2, 4}

app = FastAPI(title="Fixed Income Pricing Engine", version="0.1.0")


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

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, value: list[PortfolioPositionRequest]) -> list[PortfolioPositionRequest]:
        """Ensure at least one position is supplied."""
        if not value:
            raise ValueError("positions must not be empty")
        return value


def _build_bond(spec: BondSpec) -> FixedRateBond:
    """Construct a fixed-rate bond from a request spec."""
    try:
        return FixedRateBond(
            face_value=spec.face,
            coupon_rate=spec.coupon_rate,
            maturity_date=spec.maturity,
            issue_date=spec.issue_date,
            frequency=spec.frequency,
            day_count_convention=spec.day_count,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok"}


@app.post("/bond/price")
def price_bond(request: BondPriceRequest) -> dict[str, float]:
    """Price a bond from a yield."""
    bond = _build_bond(request)
    settlement_date = request.settlement_date or request.issue_date
    try:
        dirty_price = bond.dirty_price(yield_=request.yield_, settlement_date=settlement_date)
        clean_price = bond.clean_price(yield_=request.yield_, settlement_date=settlement_date)
        accrued_interest = bond.accrued_interest(settlement_date=settlement_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "dirty_price": dirty_price,
        "clean_price": clean_price,
        "accrued_interest": accrued_interest,
    }


@app.post("/bond/ytm")
def bond_ytm(request: BondYtmRequest) -> dict[str, float]:
    """Solve for bond yield to maturity from dirty price."""
    bond = _build_bond(request.bond_spec)
    try:
        ytm = bond.yield_to_maturity(dirty_price=request.dirty_price, settlement_date=request.settlement_date)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"ytm": ytm}


@app.post("/analytics/duration")
def duration_analytics(request: DurationRequest) -> dict[str, float]:
    """Return yield-based duration, DV01, and convexity analytics."""
    bond = _build_bond(request.bond_spec)
    try:
        macaulay = macaulay_duration(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        modified = modified_duration(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        bond_dv01 = dv01(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
        bond_convexity = convexity(bond=bond, yield_=request.yield_, settlement_date=request.settlement_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "macaulay": macaulay,
        "modified": modified,
        "dv01": bond_dv01,
        "convexity": bond_convexity,
    }


@app.post("/curve/bootstrap")
def bootstrap_curve(request: CurveBootstrapRequest) -> dict[str, list[float]]:
    """Bootstrap a zero curve from market instruments."""
    try:
        instruments = [
            MarketInstrument(
                instrument_type=instrument.type,
                tenor=instrument.tenor,
                rate=instrument.rate,
                settlement_days=instrument.settlement_days,
            )
            for instrument in request.instruments
        ]
        zero_curve = Bootstrapper(instruments).bootstrap()
    except (ValueError, NotImplementedError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "tenors": [float(value) for value in zero_curve.maturities.tolist()],
        "spot_rates": [float(zero_curve.spot_rate(float(t))) for t in zero_curve.maturities.tolist()],
        "discount_factors": [float(value) for value in zero_curve.discount_factors.tolist()],
    }


@app.post("/portfolio/risk")
def portfolio_risk(request: PortfolioRiskRequest) -> dict[str, object]:
    """Return aggregate portfolio risk measures and a risk report."""
    try:
        from fixed_income.portfolio.portfolio import Portfolio
    except ImportError as error:
        raise HTTPException(status_code=500, detail="Portfolio module is unavailable.") from error

    portfolio = Portfolio()
    for position in request.positions:
        bond = _build_bond(position.bond_spec)
        portfolio.add_position(bond=bond, notional=position.notional, direction=position.direction)

    try:
        curve_instruments = _default_curve_instruments()
        zero_curve = Bootstrapper(curve_instruments).bootstrap()
        total_mv = portfolio.total_market_value(zero_curve=zero_curve, settlement_date=request.settlement_date)
        total_dv01 = portfolio.portfolio_dv01(zero_curve=zero_curve, settlement_date=request.settlement_date)
        weighted_duration = portfolio.portfolio_duration(zero_curve=zero_curve, settlement_date=request.settlement_date)
        risk_report = portfolio.risk_report(zero_curve=zero_curve, settlement_date=request.settlement_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "total_mv": total_mv,
        "total_dv01": total_dv01,
        "weighted_duration": weighted_duration,
        "risk_report": risk_report.to_dict(orient="records"),
    }


def _default_curve_instruments() -> list[MarketInstrument]:
    """Return the sample market instruments used for portfolio risk."""
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
