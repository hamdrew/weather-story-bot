.PHONY: test tftest scan coverage lint format build check-env check-plan plan deploy bootstrap-plan bootstrap-deploy cost start pause clean

BUILD_DIR := build
PACKAGE_DIR := $(BUILD_DIR)/package
ZIP := $(BUILD_DIR)/lambda.zip
# The zip's base64 sha256, written by scripts/build_zip.py. plan passes it to Terraform and deploy
# checks the rebuilt zip against it.
ZIP_SHA := $(BUILD_DIR)/lambda.zip.sha256

test:
	uv run pytest

# Terraform's own tests (infra/tests/ and infra/bootstrap/tests/): offline, against a mock AWS
# provider, so they need no credentials. -backend=false and a data dir of their own keep them away
# from every environment's state and from the .terraform-<env> dirs.
tftest:
	TF_DATA_DIR=.terraform-test terraform -chdir=infra init -backend=false -input=false
	TF_DATA_DIR=.terraform-test terraform -chdir=infra test
	TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap init -backend=false -input=false
	TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap test

# Security scan of infra/ (which includes infra/bootstrap/), blocking: any failed check exits
# non-zero. A finding is fixed or suppressed inline with a reason, #checkov:skip=<ID>:<reason>, and
# the first step fails any skip that has no reason.
# Checkov is its own uv project (tools/checkov/) because it pins boto3 exactly, which the main
# project's dev tools can't share. Its version is in tools/checkov/uv.lock and Dependabot bumps
# it. --locked fails on a stale lock, and --project keeps the main .venv out of it.
scan:
	@if grep -rnE --include='*.tf' --exclude-dir='.terraform*' 'checkov:skip=' infra \
		| grep -vE 'checkov:skip=[A-Za-z0-9_]+:[[:space:]]*[^[:space:]]'; then \
		echo "Every checkov:skip needs a reason, as #checkov:skip=<ID>:<reason>" >&2; exit 1; fi
	uv run --locked --project tools/checkov checkov -d infra --framework terraform --compact --quiet --skip-download

# Terminal report with missing lines, plus an HTML report in htmlcov/.
coverage:
	uv run pytest --cov --cov-report=term-missing --cov-report=html

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	terraform -chdir=infra fmt -check -recursive

format:
	uv run ruff check --fix .
	uv run ruff format .
	terraform -chdir=infra fmt -recursive

# Vendor runtime dependencies for Lambda (python3.13, arm64) and zip them with the package.
# scripts/build_zip.py makes the zip reproducible: the same source and lockfile give the same
# bytes, so an unchanged build plans as "No changes".
build: clean
	mkdir -p $(PACKAGE_DIR)
	uv export --no-dev --no-emit-project --frozen -o $(BUILD_DIR)/requirements.txt
	uv pip install -r $(BUILD_DIR)/requirements.txt --target $(PACKAGE_DIR) \
		--python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary :all:
	cp -R src/weather_story_bot $(PACKAGE_DIR)/
	find $(PACKAGE_DIR) -name '__pycache__' -type d -prune -exec rm -rf {} +
	uv run --no-project python scripts/build_zip.py $(PACKAGE_DIR) $(ZIP) > $(ZIP_SHA)
	@echo "Built $(ZIP) ($$(cat $(ZIP_SHA)))"

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

# Fail before the build when there is nothing to apply.
check-plan:
	@test -f infra/$(PLAN_FILE) || { echo "No saved plan (infra/$(PLAN_FILE)). Run make plan ENV=$(ENV) first." >&2; exit 1; }

# Save the plan so deploy applies exactly what was reviewed. Terraform refuses a plan that has
# gone stale (state changed since it was made), and deploy fails if there is no plan to apply.
# -var environment comes last: the last value wins, so a stray line in a tfvars file can't
# make the environment disagree with the backend.
# plan builds first: the zip's hash is a plan input, so a plan always describes the code it was
# made from.
plan: check-env build
	$(TF) init -input=false -backend-config=envs/$(ENV).backend.hcl
	$(TF) plan -var-file=envs/$(ENV).tfvars -var lambda_zip_sha256=$$(cat $(ZIP_SHA)) \
		-var environment=$(ENV) -out=$(PLAN_FILE)

# deploy rebuilds and refuses to apply if the new zip isn't the one the plan was made for (source
# changed since the plan), so the plan and the code can't disagree. It also runs init, so a fresh
# machine can apply a plan it only downloaded.
deploy: check-env check-plan build
	$(TF) init -input=false -backend-config=envs/$(ENV).backend.hcl
	@planned=$$($(TF) show -json $(PLAN_FILE) | uv run --no-project python -c \
		'import json, sys; print(json.load(sys.stdin)["variables"]["lambda_zip_sha256"]["value"])') \
		|| exit 1; \
	built=$$(cat $(ZIP_SHA)); \
	[ "$$planned" = "$$built" ] || { \
		echo "The zip just built ($$built) is not the one planned ($$planned). Run make plan ENV=$(ENV) again." >&2; \
		exit 1; }
	$(TF) apply $(PLAN_FILE)
	rm infra/$(PLAN_FILE)

# The bootstrap stack (infra/bootstrap/): the GitHub OIDC provider, the CI roles, their permissions
# boundaries and the artifacts bucket. It is applied by hand with the weather-deploy profile's MFA,
# never by the pipeline, so the pipeline can't widen its own permissions. The same saved-plan
# pattern as ENV, with one stack: backend.hcl and bootstrap.tfvars (copy the .example files)
# and a data dir of its own, infra/bootstrap/.terraform-bootstrap/.
BS := TF_DATA_DIR=.terraform-bootstrap terraform -chdir=infra/bootstrap
BS_PLAN_FILE := deploy-bootstrap.tfplan

bootstrap-plan:
	@test -f infra/bootstrap/override.tf || { echo "No infra/bootstrap/override.tf: without it the plan would use whatever credentials are ambient. cp infra/override.tf infra/bootstrap/override.tf" >&2; exit 1; }
	$(BS) init -input=false -backend-config=backend.hcl
	$(BS) plan -input=false -var-file=bootstrap.tfvars -out=$(BS_PLAN_FILE)

bootstrap-deploy:
	@test -f infra/bootstrap/$(BS_PLAN_FILE) || { echo "No saved plan (infra/bootstrap/$(BS_PLAN_FILE)). Run make bootstrap-plan first." >&2; exit 1; }
	$(BS) init -input=false -backend-config=backend.hcl
	$(BS) apply $(BS_PLAN_FILE)
	rm infra/bootstrap/$(BS_PLAN_FILE)

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
