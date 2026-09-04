# Contributing to Weather Story Bot

Thank you for contributing. This public project handles external APIs and
Telegram delivery, so changes must remain safe, reviewable, and free of
sensitive data.

1. Fork the repository and create a focused branch.
2. Install the pinned toolchain with `mise install`, then run `uv sync`.
3. Follow the approved AI-DLC work obligation and add focused tests for behavior changes.
4. Run `make format` and `make check`.
5. Open a pull request using the supplied template.

Production dependencies must use `uv sync --locked --no-dev`. Do not edit
`uv.lock` manually; include it whenever dependency inputs change.

Never commit tokens, AWS credentials, private Telegram identifiers, invite
links, raw request/response bodies, production configuration, or sensitive
logs. Development Telegram operations must remain mock-only.

After repository bootstrap, all changes merge by pull request. Workflow,
infrastructure, IAM/OIDC, secret, deployment, and release-policy changes need
the applicable `CODEOWNERS` review.

By contributing, you agree that contributions are licensed under the
[Apache License 2.0](LICENSE).
