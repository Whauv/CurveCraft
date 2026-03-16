"""Validation script for Phase 9 test coverage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = [
    "tests/test_bonds.py",
    "tests/test_curves.py",
    "tests/test_analytics.py",
    "tests/test_portfolio.py",
    "tests/test_visualization.py",
    "tests/test_api.py",
]


def main() -> None:
    """Run the full project test suite required by the completed phases."""
    command = [sys.executable, "-m", "pytest", *TEST_FILES, "-q", "-p", "no:cacheprovider"]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print("Phase 9 validation passed.")


if __name__ == "__main__":
    main()
