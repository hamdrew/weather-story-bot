.PHONY: test coverage lint format build plan deploy cost clean

BUILD_DIR := build
PACKAGE_DIR := $(BUILD_DIR)/package
ZIP := $(BUILD_DIR)/lambda.zip

test:
	uv run pytest

# Terminal report with missing lines, plus an HTML report in htmlcov/.
coverage:
	uv run pytest --cov --cov-report=term-missing --cov-report=html

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	terraform -chdir=infra fmt -check

format:
	uv run ruff check --fix .
	uv run ruff format .
	terraform -chdir=infra fmt

# Vendor runtime dependencies for Lambda (python3.13, arm64) and zip them with the package.
build: clean
	mkdir -p $(PACKAGE_DIR)
	uv export --no-dev --no-emit-project --frozen -o $(BUILD_DIR)/requirements.txt
	uv pip install -r $(BUILD_DIR)/requirements.txt --target $(PACKAGE_DIR) \
		--python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary :all:
	cp -R src/weather_story_bot $(PACKAGE_DIR)/
	find $(PACKAGE_DIR) -name '__pycache__' -type d -prune -exec rm -rf {} +
	cd $(PACKAGE_DIR) && zip -qr ../lambda.zip .
	@echo "Built $(ZIP)"

# Save the plan so deploy applies exactly what was reviewed. Terraform refuses a plan that has
# gone stale (state changed since it was made), and deploy fails if there is no plan to apply.
plan:
	terraform -chdir=infra plan -out=deploy.tfplan

deploy:
	terraform -chdir=infra apply deploy.tfplan
	rm infra/deploy.tfplan

# Estimated monthly cost of infra/ for 1 office, 6 offices and all 122 US offices (no AWS credentials).
# scripts/infracost_usage.py writes one usage file per scenario, infracost.yml scans infra/ once per
# file, and the report prints full-precision costs side by side (Infracost's tables round to dollars).
cost:
	@command -v infracost >/dev/null || { echo "infracost not found; see 'Cost estimate' in README.md for setup" >&2; exit 1; }
	@uv run python scripts/infracost_usage.py write $(BUILD_DIR)
	infracost scan --json > $(BUILD_DIR)/infracost.json
	@uv run python scripts/infracost_usage.py report $(BUILD_DIR)/infracost.json

clean:
	rm -rf $(BUILD_DIR)
