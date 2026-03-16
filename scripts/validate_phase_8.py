"""Validation script for Phase 8 FastAPI endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from fixed_income.api.main import app


def main() -> None:
    """Run the required Phase 8 API validation checks."""
    client = TestClient(app)

    health = client.get("/health")
    print("health:", health.json())
    if health.status_code != 200:
        raise SystemExit("Health endpoint validation failed.")

    price = client.post(
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
    print("bond/price:", price.json())
    if price.status_code != 200:
        raise SystemExit("Bond price endpoint validation failed.")

    duration = client.post(
        "/analytics/duration",
        json={
            "bond_spec": {
                "face": 1000.0,
                "coupon_rate": 0.06,
                "maturity": "2035-01-01",
                "issue_date": "2025-01-01",
                "frequency": 2,
                "day_count": "ACT/ACT",
            },
            "yield": 0.06,
            "settlement_date": "2025-01-01",
        },
    )
    print("analytics/duration:", duration.json())
    if duration.status_code != 200:
        raise SystemExit("Duration endpoint validation failed.")

    print("Phase 8 validation passed.")


if __name__ == "__main__":
    main()
