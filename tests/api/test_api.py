"""API and dashboard tests."""

from __future__ import annotations

import importlib

import pytest


def _load_api_components() -> dict[str, object]:
    """Load API callables and schemas, skipping cleanly if FastAPI is unavailable."""
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # pragma: no cover - local broken env fallback
        pytest.skip(f"FastAPI installation is incomplete in this environment: {exc}")

    try:
        api_main = importlib.import_module("fixed_income.api.main")
        api_schemas = importlib.import_module("fixed_income.api.schemas")
    except Exception as exc:  # pragma: no cover - local broken env fallback
        pytest.skip(f"FastAPI application modules are unavailable in this environment: {exc}")

    return {
        "TestClient": TestClient,
        "app": api_main.app,
        "bond_dashboard": api_main.bond_dashboard,
        "bond_curve_price_dashboard": api_main.bond_curve_price_dashboard,
        "bond_ytm": api_main.bond_ytm,
        "bootstrap_curve": api_main.bootstrap_curve,
        "curve_dashboard": api_main.curve_dashboard,
        "dashboard_config": api_main.dashboard_config,
        "duration_analytics": api_main.duration_analytics,
        "hedge_dashboard": api_main.hedge_dashboard,
        "health": api_main.health,
        "key_rate_dashboard": api_main.key_rate_dashboard,
        "portfolio_dashboard": api_main.portfolio_dashboard,
        "portfolio_risk": api_main.portfolio_risk,
        "price_bond": api_main.price_bond,
        "BondDashboardRequest": api_schemas.BondDashboardRequest,
        "BondCurvePriceRequest": api_schemas.BondCurvePriceRequest,
        "BondPriceRequest": api_schemas.BondPriceRequest,
        "BondSpec": api_schemas.BondSpec,
        "BondYtmRequest": api_schemas.BondYtmRequest,
        "CurveBootstrapRequest": api_schemas.CurveBootstrapRequest,
        "CurveDashboardRequest": api_schemas.CurveDashboardRequest,
        "CurveInstrumentRequest": api_schemas.CurveInstrumentRequest,
        "DurationRequest": api_schemas.DurationRequest,
        "HedgeAnalysisRequest": api_schemas.HedgeAnalysisRequest,
        "KeyRateRequest": api_schemas.KeyRateRequest,
        "PortfolioDashboardRequest": api_schemas.PortfolioDashboardRequest,
        "PortfolioPositionRequest": api_schemas.PortfolioPositionRequest,
        "PortfolioRiskRequest": api_schemas.PortfolioRiskRequest,
    }


def _sample_curve_instruments(curve_instrument_request) -> list[object]:
    """Return a reusable set of sample curve instruments."""
    return [
        curve_instrument_request(type="deposit", tenor="1M", rate=0.05),
        curve_instrument_request(type="deposit", tenor="3M", rate=0.051),
        curve_instrument_request(type="deposit", tenor="6M", rate=0.0515),
        curve_instrument_request(type="deposit", tenor="1Y", rate=0.052),
        curve_instrument_request(type="swap", tenor="2Y", rate=0.0525),
        curve_instrument_request(type="swap", tenor="5Y", rate=0.053),
        curve_instrument_request(type="swap", tenor="10Y", rate=0.0535),
        curve_instrument_request(type="swap", tenor="30Y", rate=0.054),
    ]


def test_dashboard_homepage_serves_html() -> None:
    """The dashboard homepage should render the curated UI shell."""
    components = _load_api_components()
    client = components["TestClient"](components["app"])
    response = client.get("/")
    assert response.status_code == 200
    assert ("Price a Bond" in response.text) or ("Price Bond" in response.text)
    assert ("Build a Curve" in response.text) or ("Build Curve" in response.text)
    assert ("Analyze a Portfolio" in response.text) or ("Portfolio Risk" in response.text)


def test_dashboard_config_returns_samples() -> None:
    """The dashboard config endpoint should expose sample payloads and supported options."""
    components = _load_api_components()
    response = components["dashboard_config"]()
    assert response.frequency_options == [1, 2, 4]
    assert "sample_bond_request" in response.model_dump()


def test_health_endpoint() -> None:
    """Health endpoint should return an ok status."""
    components = _load_api_components()
    assert components["health"]() == {"status": "ok", "service": "curvecraft-api"}


def test_bond_price_endpoint() -> None:
    """Bond pricing endpoint should return price components."""
    components = _load_api_components()
    response = components["price_bond"](
        components["BondPriceRequest"].model_validate(
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


def test_bond_dashboard_endpoint() -> None:
    """The dashboard bond endpoint should return metrics and chart-ready series."""
    components = _load_api_components()
    response = components["bond_dashboard"](
        components["BondDashboardRequest"].model_validate(
            {
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
                "price_yield_points": 21,
            }
        )
    )
    assert response.clean_price > 0.0
    assert len(response.price_yield_yields) == 21
    assert len(response.cash_flows) > 0


def test_bond_ytm_endpoint() -> None:
    """Bond YTM endpoint should recover par yield."""
    components = _load_api_components()
    response = components["bond_ytm"](
        components["BondYtmRequest"](
            bond_spec=components["BondSpec"](
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
    components = _load_api_components()
    response = components["bootstrap_curve"](
        components["CurveBootstrapRequest"](
            instruments=_sample_curve_instruments(components["CurveInstrumentRequest"])[:6]
        )
    )
    assert response.tenors[0] == 0.0
    assert response.discount_factors[0] == 1.0


def test_curve_dashboard_endpoint() -> None:
    """The dashboard curve endpoint should return curve views and shifted overlays."""
    components = _load_api_components()
    response = components["curve_dashboard"](
        components["CurveDashboardRequest"](
            instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
            max_maturity=30.0,
            grid_points=48,
            scenario_parallel_shift_bps=20.0,
        )
    )
    assert len(response.nodes) >= 2
    assert len(response.curve_maturities) == 48
    assert len(response.shifted_spot_rates) == 48
    assert "parallel_up_10bps" in response.scenario_rates


def test_bond_curve_price_endpoint() -> None:
    """Curve-based pricing endpoint should return metrics for requested bonds."""
    components = _load_api_components()
    response = components["bond_curve_price_dashboard"](
        components["BondCurvePriceRequest"](
            bond_spec=components["BondSpec"](
                face=1000.0,
                coupon_rate=0.05,
                maturity="2035-01-01",
                issue_date="2025-01-01",
                frequency=2,
                day_count="ACT/ACT",
            ),
            settlement_date="2025-01-01",
            curve_instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
        )
    )
    assert response.curve_source == "request"
    assert len(response.metrics) >= 1


def test_key_rate_dashboard_endpoint() -> None:
    """Dedicated key-rate endpoint should return bucket map and totals."""
    components = _load_api_components()
    response = components["key_rate_dashboard"](
        components["KeyRateRequest"](
            bond_spec=components["BondSpec"](
                face=1000.0,
                coupon_rate=0.05,
                maturity="2035-01-01",
                issue_date="2025-01-01",
                frequency=2,
                day_count="ACT/ACT",
            ),
            settlement_date="2025-01-01",
            curve_instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
            bump_bps=1.0,
        )
    )
    assert "10Y" in response.key_rate_dv01
    assert response.total_curve_dv01 > 0.0


def test_hedge_dashboard_endpoint() -> None:
    """Hedge endpoint should produce a required notional to hit target DV01."""
    components = _load_api_components()
    response = components["hedge_dashboard"](
        components["HedgeAnalysisRequest"](
            positions=[
                components["PortfolioPositionRequest"](
                    bond_spec=components["BondSpec"](
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
            target_dv01=0.0,
            hedge_bond_spec=components["BondSpec"](
                face=1000.0,
                coupon_rate=0.06,
                maturity="2038-01-01",
                issue_date="2025-01-01",
                frequency=2,
                day_count="ACT/ACT",
            ),
            curve_instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
        )
    )
    assert response.hedge_bond_unit_dv01 > 0.0


def test_duration_endpoint() -> None:
    """Duration analytics endpoint should return all requested measures."""
    components = _load_api_components()
    response = components["duration_analytics"](
        components["DurationRequest"].model_validate(
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
    components = _load_api_components()
    response = components["portfolio_risk"](
        components["PortfolioRiskRequest"](
            positions=[
                components["PortfolioPositionRequest"](
                    bond_spec=components["BondSpec"](
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
    components = _load_api_components()
    response = components["portfolio_risk"](
        components["PortfolioRiskRequest"](
            positions=[
                components["PortfolioPositionRequest"](
                    bond_spec=components["BondSpec"](
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
            curve_instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
        )
    )
    assert response.curve_source == "request"


def test_portfolio_dashboard_endpoint() -> None:
    """The dashboard portfolio endpoint should return risk rows and scenario outputs."""
    components = _load_api_components()
    response = components["portfolio_dashboard"](
        components["PortfolioDashboardRequest"](
            positions=[
                components["PortfolioPositionRequest"](
                    bond_spec=components["BondSpec"](
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
            curve_instruments=_sample_curve_instruments(components["CurveInstrumentRequest"]),
            scenario_parallel_shift_bps=25.0,
        )
    )
    assert response.total_mv > 0.0
    assert len(response.risk_report) == 1
    assert len(response.key_rate_profile) >= 1
