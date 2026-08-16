# NWS source-contract fixtures

These sanitized fixtures capture the supported response shapes used by the
ingestion unit and contract tests. They intentionally preserve field names and
JSON nesting from the public NWS API while omitting large operational arrays.

- `office_mkx.v1.json` is the flat JSON-LD shape returned by
  `/offices/MKX`.
- `regional_office_crh.v1.json` is the referenced `parentOrganization`
  resource returned by `/offices/CRH`.
- `weatherstories_mkx_success.v1.json` and `weatherstories_mkx_empty.v1.json`
  cover non-empty and empty Weather Story collections.

Refresh these fixtures deliberately when the upstream contract changes. Do
not add credentials, tokens, private destinations, or unbounded upstream
payloads.
