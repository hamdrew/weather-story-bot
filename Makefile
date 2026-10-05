.PHONY: test coverage lint format build check-env plan deploy cost start pause clean

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

# One ENV (production or staging, no default) selects the backend config, var file, data dir and
# plan file together, so they can't disagree. Each environment has its own data dir: a shared
# .terraform/ remembers its last backend, and forgetting -reconfigure would point a staging plan at
# production's state. TF_DATA_DIR is relative to -chdir, so it lands in infra/.terraform-<env>/.
TF := TF_DATA_DIR=.terraform-$(ENV) terraform -chdir=infra
PLAN_FILE := deploy-$(ENV).tfplan

# ENV must come from the command line: make would otherwise take an exported ENV from the shell,
# and a bare `make plan` would quietly target whatever it held.
check-env:
	@case "$(origin ENV):$(ENV)" in "command line:production"|"command line:staging") ;; \
		*) echo "ENV must be production or staging on the command line, e.g. make plan ENV=staging" >&2; exit 2 ;; esac

# Save the plan so deploy applies exactly what was reviewed. Terraform refuses a plan that has
# gone stale (state changed since it was made), and deploy fails if there is no plan to apply.
# -var environment comes last: the last value wins, so a stray line in a tfvars file can't
# make the environment disagree with the backend.
plan: check-env
	$(TF) init -input=false -backend-config=envs/$(ENV).backend.hcl
	$(TF) plan -var-file=envs/$(ENV).tfvars -var environment=$(ENV) -out=$(PLAN_FILE)

deploy: check-env
	$(TF) apply $(PLAN_FILE)
	rm infra/$(PLAN_FILE)

# Estimated monthly cost of infra/ for 1 office, 6 offices and all 122 US offices (no AWS credentials).
# scripts/infracost_usage.py writes one usage file per scenario, infracost.yml scans infra/ once per
# file, and the report prints full-precision costs side by side (Infracost's tables round to dollars).
cost:
	@command -v infracost >/dev/null || { echo "infracost not found; see 'Cost estimate' in README.md for setup" >&2; exit 1; }
	@uv run python scripts/infracost_usage.py write $(BUILD_DIR)
	infracost scan --json > $(BUILD_DIR)/infracost.json
	@uv run python scripts/infracost_usage.py report $(BUILD_DIR)/infracost.json

# Start or pause an environment: its schedule and its alarm actions, which Terraform creates
# (DISABLED, and on) and then ignores (scripts/set_run_state.py explains the order and the idempotence). The names
# and region come from the environment's outputs, which need a deploy of this version first. Needs
# the weather-deploy profile's MFA code, so run it in a real terminal. bash for pipefail.
start pause: SHELL := bash
start pause: check-env
	set -o pipefail; $(TF) output -json | \
		uv run python scripts/set_run_state.py $@ --apply -

clean:
	rm -rf $(BUILD_DIR)
