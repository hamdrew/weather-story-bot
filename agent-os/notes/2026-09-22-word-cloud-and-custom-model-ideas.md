# Word Cloud and Custom Model: Ideas

Date: 2026-09-22. Status: captured only, not triaged into the roadmap. Nothing here is decided
or built. Surfaced mid-session, explicitly out of scope for the Phase 1.2 work underway; came up
while reviewing the Task 6 CLI rewrite.

## 1. A word cloud, as part of analytics

Fits the Year in Review's existing "craft" fact category (`2026-09-16-year-in-review-ideas.md`,
§2 already lists "most common title words"). A word cloud over story titles and/or descriptions,
per office or per year, would be a fun (if a bit dated-feeling) visual alongside the deterministic
facts already planned there.

- Could reuse the same derived-facts pipeline (`scripts/build_analytics.py`) rather than being a
  separate thing — word frequency is a deterministic fact, not an inference
- "Dated-feeling" was the user's own hedge — worth a gut-check at build time on whether it earns
  its place in the PDF, or is more of a fun bonus/Easter egg than a headline visual
- No decision on library, styling, or whether it's per-office or aggregate

## 2. Personal learning project: a custom model trained on story text/images

**Explicitly a personal side project, not a product feature.** The user was clear on both
guardrails, stated directly:

- Never intended to imply it could replace the meteorologists who write the real Weather Stories
- The user would **not share it with the NWS offices** — this stays personal

The idea: train or fine-tune a model on the archive's own data — the message text that goes out
(captions/descriptions) and/or the story images ("slides") — to generate fake stories, or
plausible real-sounding ones, based on weather conditions. The stated motivation is learning how
to train/fine-tune a custom model, for the user's job (ties to the existing "Cloud AI learning
goal" memory), with generating stories as the fun output rather than the point.

- The S3 archive (`backend/archive-layout`) is the natural data source — every revision's image
  and text, already captured, already a source of truth
- Distinct from the Year in Review's Bedrock **inference** work (labeling, narrative generation
  over computed facts) — this is a from-scratch/fine-tuned **generation** model, a different kind
  of project, likely `aws-ai-ml`/SageMaker territory rather than Bedrock's managed-model APIs
- No decision on approach (fine-tune vs. train from scratch), scope, or timeline — this is much
  earlier-stage than the Year in Review ideas, more "a thing to eventually play with" than a spec
  candidate yet
