# Contributing to ctxclipper

## Development Setup

```bash
git clone https://github.com/ctxclipper/ctxclipper.git
cd ctxclipper
pip install -e ".[dev,tokens]"
```

## Local Quality Checks

```bash
pytest --cov=ctxclipper --cov-report=term-missing
ruff check ctxclipper tests
ruff format --check ctxclipper tests
mypy ctxclipper
python -m build
twine check dist/*
```

## Pull Requests

1. Keep changes focused and include tests for behavior changes.
2. Update `README.md` and `CHANGELOG.md` when user-facing behavior changes.
3. Ensure CI is green before requesting review.

## Release Process

1. Update `CHANGELOG.md` and bump version in `pyproject.toml` and `ctxclipper/__init__.py`.
2. Run all local quality checks.
3. Commit and tag a release: `git tag vX.Y.Z`.
4. Push commit and tag: `git push && git push --tags`.
5. GitHub Actions publishes to PyPI when a `v*` tag reaches `main`.
