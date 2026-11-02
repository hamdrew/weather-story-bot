# Tech Stack Decisions: u1-logging-review

## Sources

- `inception/codekb` technology stack: `aidlc/spaces/default/codekb/weather-story-bot/technology-stack.md`
- `functional-design/functional-spec.md` (W3, run.slow) and `rules.md` (BR4.1)
- `inception/requirements-analysis/requirements.md`: NFR1, NFR4, NFR6

## Decisions

| ID | Decision | Rationale | Alternatives rejected |
|----|----------|-----------|----------------------|
| NFR6.1 | The review is one Markdown file, `docs/logging-review.md`, in a new `docs/` folder. | FR6.1 asks for a written review in the repository; Markdown needs no tooling and renders on GitHub. | A section in `README.md` (grows without bound); a file under `aidlc/` (only the AI-DLC record, not the project's own documentation). |
| NFR1.1 | No new AWS resource, dependency or tool. The unit changes no code. | The review costs nothing to run; the added cost of what it decides belongs to U3 to U5. | none |
| NFR4.3 | (A requirement on U2's code, not on U1's document.) `run.slow` times the run with `time.monotonic` from the standard library. | A monotonic clock cannot step backwards; a standard-library call adds no dependency, so httpx stays the only runtime dependency. | `datetime.now` (wall clock, can step); a CloudWatch Duration alarm or anomaly detection (the owner asked; ruled out in the functional design as more scope and a poor fit for run times that depend on the number of posts). |
| NFR6.2 | The review lands in its own pull request and merges to `main`; the pipeline deploys nothing because no code or Terraform changes. | Team practice: one revertible slice per pull request. | Bundling with U2 (a larger change to watch after merge). |

## Unchanged

Python 3.13, httpx 0.28.1 as the only runtime dependency, boto3 dev-only, Terraform `~> 1.11`, pytest and respx for
offline tests, ruff and ty for lint. The unit leaves them as they are.
