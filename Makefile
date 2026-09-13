.PHONY: test coverage lint format build plan deploy clean

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
	terraform -chdir=infra fmt -check

format:
	uv run ruff check --fix .
	uv run ruff format .
	terraform -chdir=infra fmt

# Vendor runtime dependencies for Lambda (python3.13, arm64) and zip them with the package.
build: clean
	mkdir -p $(PACKAGE_DIR)
	uv export --no-dev --no-hashes --no-emit-project --frozen -o $(BUILD_DIR)/requirements.txt
	uv pip install -r $(BUILD_DIR)/requirements.txt --target $(PACKAGE_DIR) \
		--python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary :all:
	cp -R src/weather_story_bot $(PACKAGE_DIR)/
	find $(PACKAGE_DIR) -name '__pycache__' -type d -prune -exec rm -rf {} +
	cd $(PACKAGE_DIR) && zip -qr ../lambda.zip .
	@echo "Built $(ZIP)"

plan:
	terraform -chdir=infra plan

deploy:
	terraform -chdir=infra apply

clean:
	rm -rf $(BUILD_DIR)
