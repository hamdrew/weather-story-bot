# Reverse Engineering Timestamp

## Run Record

- Date: 2026-10-30T03:11:53Z
- Commit: 657c6f08f0f48d489682544a05c5e3f9e51c8e35
- Kind: first full scan of the repository, Minimal depth, for intent `agentos-to-aidlc`.
- Not opened (left out of the block): `.venv/`, `build/`, `infra/.terraform*/`, `infra/bootstrap/.terraform*/`, tool caches, gitignored local files (`.env`, `infra/envs/*.tfvars`, `*.backend.hcl`, `override.tf`, `*.tfplan`), and AI-DLC's own install and workspace (`.claude/`, `aidlc/`, `aidlc.settings.json`, `.mcp.json`).

## Scope of Analysis

```yaml
scope_version: 1
kind: full
intent: agentos-to-aidlc
fingerprint: 9b68a1f3b3924374f9a2e3941feb8531356049ed
analyzed:
  paths:
    - ./
  components:
    - Lambda Handler
    - Dry-Run CLI
    - Config
    - Story Model
    - NWS Client
    - Planner
    - State Store
    - Story History
    - Story Archive
    - Telegram Client
    - Operator Scripts
    - Main Infrastructure Stack
    - Bootstrap Stack
    - Task Runner
    - CI/CD Pipeline
    - Test Suites
    - Agent OS Planning Record
shallow:
  paths:
    - scripts/migrate_story_keys.py
    - scripts/migrate_table_keys.py
    - scripts/infracost_usage.py
    - tests/
    - infra/tests/
    - infra/bootstrap/tests/
    - agent-os/specs/
    - agent-os/notes/
    - agent-os/standards/
    - assets/
```
