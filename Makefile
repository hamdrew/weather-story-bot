.PHONY: check format lint test typecheck sync sync-production

sync:
	uv sync

# Deployment and packaging must never resolve or update dependencies.
sync-production:
	uv sync --locked --no-dev

format:
	uv run --locked ruff format src tests

lint:
	uv run --locked ruff check src tests

typecheck:
	uv run --locked mypy

test:
	uv run --locked pytest

check: lint typecheck test
