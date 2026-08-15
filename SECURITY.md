# Security Policy

## Reporting a vulnerability

Do **not** report vulnerabilities in public GitHub issues, discussions, pull
requests, logs, release assets, or comments.

Use [private GitHub Security Advisories](https://github.com/hamdrew/weather-story-bot/security/advisories/new).
If unavailable, contact [@hamdrew](https://github.com/hamdrew) privately. Do
not include Telegram tokens, AWS credentials, secret values, private IDs,
invite links, or raw production logs. Rotate or revoke exposed credentials
before sending a sanitized report.

## Credential exposure

Treat a suspected credential exposure as an incident. Never paste the exposed
value into GitHub. Use this sequence:

1. Revoke or rotate the credential at its issuing service and invalidate any
   dependent sessions or access keys.
2. Remove the credential from the affected service configuration, artifacts,
   and logs without rewriting public history as a substitute for rotation.
3. Review sanitized audit evidence to determine the exposure window and scope.
4. Confirm the replacement credential works through the applicable non-public
   smoke procedure, then privately report the incident and remediation.

The detailed Telegram secret rotation and rollback procedure will be maintained
with the deployment runbook. Until then, do not attempt to rotate a production
credential from a workstation or disclose any credential value in the report.
