# CurveCraft

CurveCraft is a fixed income pricing and risk analytics codebase built around a Python package, a FastAPI service layer, regression tests, validation scripts, and a notebook demo.

## Setup

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Usage

Run the API locally:

```bash
python -m uvicorn fixed_income.api.main:app --reload
```

Run the full test suite:

```bash
python -m pytest tests -q -p no:cacheprovider
```

Run the notebook demo:

```bash
jupyter notebook notebooks/demo.ipynb
```

## Structure

```text
fixed_income/
├── .github/
├── docs/
├── notebooks/
├── scripts/
├── src/
│   └── fixed_income/
├── tests/
├── .env.example
├── AGENTS.md
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── README.md
└── requirements.txt
```

## Key Commands

- `python -m uvicorn fixed_income.api.main:app --reload`
- `python -m pytest tests -q -p no:cacheprovider`
- `python scripts/validate_phase_9.py`
- `python scripts/generate_readme_assets.py`

## Notes

- The source package now uses a `src/` layout.
- Local development supports the `src/` layout through [sitecustomize.py](C:\Users\prana\OneDrive\Documents\Playground\fixed_income\sitecustomize.py) and [conftest.py](C:\Users\prana\OneDrive\Documents\Playground\fixed_income\tests\conftest.py).
- Continuous integration lives in [ci.yml](C:\Users\prana\OneDrive\Documents\Playground\fixed_income\.github\workflows\ci.yml).
