# Env Config

The Lambda reads all its config from env vars through `Settings.from_env`, which raises `ConfigError` if anything is missing or invalid.

```python
@classmethod
def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings: ...
```

- Tests pass a dict instead of patching `os.environ`
- `require()` strips whitespace, and a blank value counts as missing
- Structured values are JSON (`OFFICES_JSON`), checked item by item with a message that names the problem
- Secrets: env holds the SSM parameter **name** (`TELEGRAM_TOKEN_PARAM`), never the value

## Adding a setting

In one change:

1. `Settings` field + `from_env` (`config.py`)
2. `environment.variables` in `infra/lambda.tf`
3. `infra/variables.tf` (with `validation` if constrained) + `terraform.tfvars.example`
4. A test in `tests/test_config.py`, plus the `ENV` dict in the `lambda_handler` end-to-end test

## Office ids

Validated as `^[A-Z]{3}$` in **both** `config.py` and `variables.tf`. Keep the two in sync.

- Terraform catches typos at plan time
- Python still checks, because office ids end up in NWS URLs and S3 paths (`../X` must fail), and the Lambda's env can be changed outside Terraform
- The local CLI's `--office` is only uppercased, not validated. It hits NWS only
