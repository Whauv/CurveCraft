# AGENTS

## Setup

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Folder Map

- `src/fixed_income/`: application and library code
- `tests/`: regression and API tests
- `scripts/`: validation and asset-generation scripts
- `notebooks/`: interactive demo notebook
- `docs/`: generated documentation assets

## Code Style

- Python 3.10+
- Type hints on public functions
- NumPy-style docstrings on public APIs
- Keep rates as decimals internally
- Keep dates as `datetime.date`

## Test Commands

```bash
ruff check src tests scripts
python -m pytest tests -q -p no:cacheprovider
```

## Run Commands

```bash
python -m uvicorn fixed_income.api.main:app --reload
python scripts/validate_phase_9.py
```
