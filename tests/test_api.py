"""Phase 8 API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fixed_income.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Health endpoint should return an ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bond_price_endpoint() -> None:
    """Bond pricing endpoint should return price components."""
    response = client.post(
        "/bond/price",
        json={
            "face": 1000.0,
            "coupon_rate": 0.04,
            "maturity": "2030-01-01",
            "issue_date": "2025-01-01",
            "frequency": 2,
            "day_count": "ACT/ACT",
            "yield": 0.04,
            "settlement_date": "2025-01-01",
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["dirty_price"] == pytest.approx(1000.0, abs=1e-10)
    assert body["clean_price"] == pytest.approx(1000.0, abs=1e-10)


def test_bond_ytm_endpoint() -> None:
    """Bond YTM endpoint should recover par yield."""
    response = client.post(
        "/bond/ytm",
        json={
            "bond_spec": {
                "face": 1000.0,
                "coupon_rate": 0.04,
                "maturity": "2030-01-01",
                "issue_date": "2025-01-01",
                "frequency": 2,
                "day_count": "ACT/ACT",
            },
            "dirty_price": 1000.0,
            "settlement_date": "2025-01-01",
        },
    )
    assert response.status_code == 200
    assert response.json()["ytm"] == pytest.approx(0.04, abs=1e-12)


def test_curve_bootstrap_endpoint() -> None:
    """Curve bootstrap endpoint should return curve arrays."""
    response = client.post(
        "/curve/bootstrap",
        json={
            "instruments": [
                {"type": "deposit", "tenor": "1M", "rate": 0.05},
                {"type": "deposit", "tenor": "3M", "rate": 0.051},
                {"type": "deposit", "tenor": "6M", "rate": 0.0515},
                {"type": "deposit", "tenor": "1Y", "rate": 0.052},
                {"type": "swap", "tenor": "2Y", "rate": 0.0525},
                {"type": "swap", "tenor": "5Y", "rate": 0.053},
            ]
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["tenors"][0] == 0.0
    assert body["discount_factors"][0] == 1.0


def test_portfolio_risk_endpoint() -> None:
    """Portfolio risk endpoint should return aggregate risk and report rows."""
    response = client.post(
        "/portfolio/risk",
        json={
            "positions": [
                {
                    "bond_spec": {
                        "face": 1000.0,
                        "coupon_rate": 0.05,
                        "maturity": "2032-01-01",
                        "issue_date": "2025-01-01",
                        "frequency": 2,
                        "day_count": "ACT/ACT",
                    },
                    "notional": 1000000.0,
                    "direction": 1,
                }
            ],
            "settlement_date": "2025-01-01",
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert "total_mv" in body
    assert "risk_report" in body
    assert len(body["risk_report"]) == 1
