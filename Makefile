.PHONY: check format format-markdown lint test coverage typecheck sync sync-production

sync:
	uv sync

# Deployment and packaging must never resolve or update dependencies.
sync-production:
	uv sync --locked --no-dev

format:
	uv run --locked ruff format src tests
	$(MAKE) format-markdown

format-markdown:
	find . -type f -name '*.md' -not -path './.git/*' -not -path './coverage/*' -print0 | xargs -0 npx --yes prettier --write

lint:
	uv run --locked ruff check src tests

typecheck:
	uv run --locked mypy

test:
	uv run --locked pytest

coverage: test

check: lint typecheck test
