.PHONY: check format format-markdown lint test coverage typecheck sync sync-production validate-sam

validate-sam:
	SAM_CLI_TELEMETRY=0 AWS_EC2_METADATA_DISABLED=true uv tool run --from aws-sam-cli==1.165.0 sam validate --lint --region us-east-2 --template-file template.yaml

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
