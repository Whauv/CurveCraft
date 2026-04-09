"""Service helpers for the fixed income API."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from fixed_income.bonds.bond import FixedRateBond
from fixed_income.curves.bootstrapper import MarketInstrument

from .schemas import BondSpec, CurveInstrumentRequest

DEFAULT_SETTLEMENT_DAYS = 2

logger = logging.getLogger(__name__)


def bad_request(detail: str) -> HTTPException:
    """Return a standardized bad-request error."""
    logger.warning("API bad request: %s", detail)
    return HTTPException(status_code=400, detail=detail)


def build_bond(spec: BondSpec) -> FixedRateBond:
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
        raise bad_request(str(error)) from error


def build_market_instruments(instruments: list[CurveInstrumentRequest]) -> list[MarketInstrument]:
    """Construct market instruments from request payloads."""
    try:
        return [
            MarketInstrument(
                instrument_type=instrument.type,
                tenor=instrument.tenor,
                rate=instrument.rate,
                settlement_days=instrument.settlement_days,
            )
            for instrument in instruments
        ]
    except (ValueError, NotImplementedError) as error:
        raise bad_request(str(error)) from error


def default_curve_instruments() -> list[MarketInstrument]:
    """Return the sample market instruments used for portfolio risk."""
    return [
        MarketInstrument(instrument_type="deposit", tenor="1M", rate=0.0500, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="deposit", tenor="3M", rate=0.0510, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="deposit", tenor="6M", rate=0.0515, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="deposit", tenor="1Y", rate=0.0520, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="swap", tenor="2Y", rate=0.0525, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="swap", tenor="5Y", rate=0.0530, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="swap", tenor="10Y", rate=0.0535, settlement_days=DEFAULT_SETTLEMENT_DAYS),
        MarketInstrument(instrument_type="swap", tenor="30Y", rate=0.0540, settlement_days=DEFAULT_SETTLEMENT_DAYS),
    ]
