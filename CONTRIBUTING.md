# Contributing to SAFE SIGHT AI

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Code Quality

- Run linter: `ruff check .`
- Run tests: `pytest tests/ -q`
- Run readiness check: `python scripts/prod_readiness_check.py`

## Commit Messages

Follow conventional commits: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

## Pull Request Process

1. Branch from `main`
2. Ensure `ruff check .` passes with zero errors
3. Ensure `pytest tests/ -q` passes all tests
4. Update documentation for any changed behavior
5. Request review from a maintainer
