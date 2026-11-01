# Deployment Log: agent-os to AI-DLC

All times are America/Chicago (CST) on 2026-11-01. The change reached the live environments only through
pull request #32 and the pipeline; no deploy command was run from a laptop.

## What was deployed

A behaviour-identical Lambda zip. Comments, docs and the AI-DLC setup changed; no executable statement
did. The `build-test-results` this rests on are `construction/build-and-test/test-results.md` and
`build-and-test-summary.md`: 296 tests, `terraform test`, Checkov and lint green, 99% coverage, and the
syntax-tree comparison against `657c6f0`. The only infrastructure difference is the function's code: `s3_key` and
`source_code_hash` moved from `TYC6d+Fl2fc89zfZV4GYIjdMEBH8UUcp+UjjvOJtgkU=` to
`JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=`.

## Decisions made before the deploy

| Question | Answer |
|---|---|
| Rebuild the code knowledge base before the pull request (Q1) | Yes: one Reverse Engineering rescan, then one pull request |
| Who commits, pushes and opens the pull request (Q2) | The agent did, after asking again before the commit; the owner reviewed and merged |

Pre-deployment checks: the `readonly` AWS profile saw the account (role `ReadOnly`, account `********8552`);
no data migration was involved; the staging plan showed only the Lambda code changing.

## Timeline

| Time | Event |
|---|---|
| Before the merge | Reverse Engineering rescan replaced the 9 codekb files (coverage check: COVERS). Commit `088f023` made after the owner confirmed. Branch `agentos-to-aidlc` pushed, PR #32 opened |
| PR checks | `checks`, both `plan` jobs and the CodeQL jobs passed; both plans showed `0 to add, 1 to change, 0 to destroy` |
| 1:33 PM | Owner merged PR #32 (squash commit `3d25857`) |
| 1:34 PM | `checks` on `main` passed |
| 1:35 PM | `deploy (staging)` succeeded; staging Lambda updated |
| 1:36 PM | `plan (production)` saved its plan; `deploy (production)` waited on the owner's approval in the `production` environment |
| 1:38 PM | After the owner's approval, `deploy (production)` succeeded (completed 1:38:55 PM); production Lambda updated at 1:38:46 PM |
| 1:45 PM | First scheduled production run on the new code |

Pipeline run: `41342351056`, conclusion `success`.

## Result

Both environments run `JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=`. No job failed, no rerun was needed,
and no rollback was taken.

## Rollback

Not used. If it were needed: revert `3d25857` on `main` and let the pipeline redeploy; the same source
rebuilds the same bytes at the same key. Data was untouched, and the 35-day recovery window (DynamoDB
point-in-time recovery, S3 noncurrent versions) applies as usual.
