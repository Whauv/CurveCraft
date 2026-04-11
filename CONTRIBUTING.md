# Contributing

## Getting Started

1. Install dependencies with `python -m pip install -r requirements.txt`
2. Install the package in editable mode with `python -m pip install -e .`
3. Run lint and tests before opening a pull request

## Quality Gate

```bash
ruff check src tests scripts
python -m pytest tests -q -p no:cacheprovider
```

## Pull Requests

- Keep changes focused
- Preserve existing business logic unless the task explicitly requires behavior changes
- Update documentation when commands, structure, or entry points change
