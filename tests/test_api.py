"""Phase 8 API tests."""

from __future__ import annotations

import pytest

FASTAPI_MODULE = pytest.importorskip("fastapi")
if not hasattr(FASTAPI_MODULE, "FastAPI"):
    pytest.skip("FastAPI installation is incomplete in this environment.", allow_module_level=True)

from fixed_income.api.main import (
    BondPriceRequest,
    BondSpec,
    BondYtmRequest,
    CurveBootstrapRequest,
    CurveInstrumentRequest,
    DurationRequest,
    PortfolioPositionRequest,
    PortfolioRiskRequest,
    bond_ytm,
    bootstrap_curve,
    duration_analytics,
    health,
    portfolio_risk,
    price_bond,
)


def test_health_endpoint() -> None:
    """Health endpoint should return an ok status."""
    assert health() == {"status": "ok", "service": "curvecraft-api"}


def test_bond_price_endpoint() -> None:
    """Bond pricing endpoint should return price components."""
    response = price_bond(
        BondPriceRequest.model_validate(
            {
                "face": 1000.0,
                "coupon_rate": 0.04,
                "maturity": "2030-01-01",
                "issue_date": "2025-01-01",
                "frequency": 2,
                "day_count": "ACT/ACT",
                "yield": 0.04,
                "settlement_date": "2025-01-01",
            }
        )
    )
    assert response.dirty_price == pytest.approx(1000.0, abs=1e-10)
    assert response.clean_price == pytest.approx(1000.0, abs=1e-10)


def test_bond_ytm_endpoint() -> None:
    """Bond YTM endpoint should recover par yield."""
    response = bond_ytm(
        BondYtmRequest(
            bond_spec=BondSpec(
                face=1000.0,
                coupon_rate=0.04,
                maturity="2030-01-01",
                issue_date="2025-01-01",
                frequency=2,
                day_count="ACT/ACT",
            ),
            dirty_price=1000.0,
            settlement_date="2025-01-01",
        )
    )
    assert response.ytm == pytest.approx(0.04, abs=1e-12)


def test_curve_bootstrap_endpoint() -> None:
    """Curve bootstrap endpoint should return curve arrays."""
    response = bootstrap_curve(
        CurveBootstrapRequest(
            instruments=[
                CurveInstrumentRequest(type="deposit", tenor="1M", rate=0.05),
                CurveInstrumentRequest(type="deposit", tenor="3M", rate=0.051),
                CurveInstrumentRequest(type="deposit", tenor="6M", rate=0.0515),
                CurveInstrumentRequest(type="deposit", tenor="1Y", rate=0.052),
                CurveInstrumentRequest(type="swap", tenor="2Y", rate=0.0525),
                CurveInstrumentRequest(type="swap", tenor="5Y", rate=0.053),
            ]
        )
    )
    assert response.tenors[0] == 0.0
    assert response.discount_factors[0] == 1.0


def test_duration_endpoint() -> None:
    """Duration analytics endpoint should return all requested measures."""
    response = duration_analytics(
        DurationRequest.model_validate(
            {
                "bond_spec": {
                    "face": 1000.0,
                    "coupon_rate": 0.05,
                    "maturity": "2032-01-01",
                    "issue_date": "2025-01-01",
                    "frequency": 2,
                    "day_count": "ACT/ACT",
                },
                "yield": 0.05,
                "settlement_date": "2025-01-01",
            }
        )
    )
    assert response.macaulay > 0.0
    assert response.modified > 0.0
    assert response.dv01 > 0.0
    assert response.convexity > 0.0


def test_portfolio_risk_endpoint() -> None:
    """Portfolio risk endpoint should return aggregate risk and report rows."""
    response = portfolio_risk(
        PortfolioRiskRequest(
            positions=[
                PortfolioPositionRequest(
                    bond_spec=BondSpec(
                        face=1000.0,
                        coupon_rate=0.05,
                        maturity="2032-01-01",
                        issue_date="2025-01-01",
                        frequency=2,
                        day_count="ACT/ACT",
                    ),
                    notional=1000000.0,
                    direction=1,
                )
            ],
            settlement_date="2025-01-01",
        )
    )
    assert response.total_mv > 0.0
    assert response.curve_source == "default_sample"
    assert len(response.risk_report) == 1


def test_portfolio_risk_accepts_explicit_curve() -> None:
    """Portfolio risk endpoint should accept a caller-supplied curve."""
    response = portfolio_risk(
        PortfolioRiskRequest(
            positions=[
                PortfolioPositionRequest(
                    bond_spec=BondSpec(
                        face=1000.0,
                        coupon_rate=0.05,
                        maturity="2032-01-01",
                        issue_date="2025-01-01",
                        frequency=2,
                        day_count="ACT/ACT",
                    ),
                    notional=1000000.0,
                    direction=1,
                )
            ],
            settlement_date="2025-01-01",
            curve_instruments=[
                CurveInstrumentRequest(type="deposit", tenor="1M", rate=0.04),
                CurveInstrumentRequest(type="deposit", tenor="3M", rate=0.041),
                CurveInstrumentRequest(type="deposit", tenor="6M", rate=0.0415),
                CurveInstrumentRequest(type="deposit", tenor="1Y", rate=0.042),
                CurveInstrumentRequest(type="swap", tenor="2Y", rate=0.043),
                CurveInstrumentRequest(type="swap", tenor="5Y", rate=0.044),
                CurveInstrumentRequest(type="swap", tenor="10Y", rate=0.045),
                CurveInstrumentRequest(type="swap", tenor="30Y", rate=0.046),
            ],
        )
    )
    assert response.curve_source == "request"
