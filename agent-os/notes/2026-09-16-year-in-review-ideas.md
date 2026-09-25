# Year in Review: Ideas

Date: 2026-09-16. Status: **triaged 2026-09-20 into the roadmap** — the data capture this depends on is phase **1.2**, and the review itself is phase **3**. Still ideas for a future spec (`agent-os:shape-spec`); nothing here is decided or built unless it's marked **Decided**. Related: `2026-09-16-standards-review.md` (ledger, DynamoDB keys, analytics layout).

## Intent

Weather Stories are made by people, often overnight with weather on the way. The Year in Review celebrates **the stories and the people behind them**, from a reader's point of view. Facts about the bot's machinery belong only when they make a good story ("The Great Outage of May 16"), not as ops metrics.

It might be shared with the NWS offices themselves, so the tone is appreciation.

## Decisions so far

- **Decided: output.** A Telegram message per office that links to (or attaches) a **PDF infographic**, styled after the look of Weather Story graphics.
- **Decided: scope.** Everything is designed for N offices; MKX is built and polished first.
- **Decided: record "last seen".** It's cheap and enables "pulled early" and "lived longest".
- **Decided: inference runs after the fact.** Bedrock runs over the archive, never in the posting Lambda.

## Fact catalog

### 1. The calendar (deterministic)

- Busiest and quietest days, weeks and months
- Longest stretch with no active story; first and last story of the year
- **Holidays:** stories on or around US holidays ("Thanksgiving: 2 stories, both lake-effect snow"). Uses the office's local time zone and the `holidays` package (analytics-only dependency)
- **When forecasters publish:** a local hour-of-day histogram ("14 stories went up between midnight and 5 AM")
- Weekday vs weekend

### 2. The craft (deterministic, from revisions + first/last seen)

- Most revised story, and what changed (image, text or both)
- **The fastest fix:** a text revision minutes after the previous one with a tiny edit distance. Frame it kindly ("caught it in 4 minutes")
- Longest-running story; stories extended past their original `endTime`; stories pulled before `endTime`
- Description length, longest story, most common title words
- Alt text coverage, as appreciation ("98% of stories had alt text")

### 3. The weather (deterministic joins with external records)

- "Stories posted during the July 8 tornado outbreak": join by date + office area with historical warnings (Iowa Environmental Mesonet) and storm reports (SPC). **Check** coverage, formats and terms before relying on them. No runtime capture needed; backfill at build time
- **Drama index** (data only): severe keywords ("tornado", "life-threatening"), the `priority` flag, the red/orange share of the image's pixels, revision count
- Seasonal arc: first snow story, first severe story, first heat story

### 4. The bot's saga (machinery told as a story)

- "THE GREAT OUTAGE OF MAY 16: NWS unreachable for 5h 45m. We missed nothing." Or: "...one story came and went while we weren't looking"
- "The day NWS posted the same story twice" (rejections)
- Keep this section short. It's a sidebar, not the headline

### 5. Inferred (Bedrock, cached, labeled as such)

- Per story: hazard type, season, a drama rating, a one-line image description
- Per year: narrative text written *from computed facts*
- Candidates: "most dramatic story", "calmest week", recurring themes, a friendly look at title wordplay
- **Design flair** (added 2026-09-25): stories where someone at the office had fun with the graphic.
  Prompted by MKX's "Nice Weekend on Tap!" (start 2026-09-25T19:28Z, Telegram message 62, archived
  at `stories/MKX/2026/09/25/1928Z-nice-weekend-on-tap-36b1559a/2d1c64f41d0a986c`): a 70s
  sunburst, slab display type and a halftone texture on an unremarkable forecast. Its alt text
  is "Graphic showing a three day forecast for this weekend with nice weather conditions." That
  is accurate and says nothing about the design. Alt text describes what a story says, not how it
  looks, so the flair is only in the pixels. This story is the first test case. Two parts:
  - *Inferred, per image:* descriptive tags only: layout (house template or custom), type
    (standard or display/novelty), and a motif when there is one ("retro 70s", "holiday",
    "pop-culture reference"). The model describes; it doesn't decide what's unusual
  - *Deterministic, per office:* "unusual" means unusual **for that office**, since each office has
    its own house template. Measure each image's distance from its office's typical look (image
    embeddings, or a perceptual hash as a cheap baseline). The template clusters tightly and a
    one-off like this lands far outside, so "unusual" is a computed fact the grounding check can
    verify, not a model's opinion
  - In the PDF: an appreciation page ("the stories where someone had fun"), motifs marked as
    inferred. Not a ranking of anyone's work

## Data needed vs captured

| Data | Needed for | Captured today | Plan |
|---|---|---|---|
| Raw story JSON + image per revision | nearly everything | Yes (S3 archive) | Keep |
| Posted/updated/rejected/deleted events with time | craft, saga | Latest revision only; rejections only in 30-day logs | Ledger (standards review) |
| First seen / last seen per story | pulled early, lifespan | No | Record; update `last_seen_at` when it's at least about 1h stale |
| Per-run outcomes per office | outages | 30-day logs only | **Daily run record** (below) |
| Office time zone | holidays, hour of day, year boundaries | No | Office config (standards review) |
| Historical warnings / storm reports | weather joins | No | Fetch at build time from public sources |
| Inference labels | inferred facts | No | Derived dataset, keyed by model + prompt version |
| Image embeddings per revision | design flair | No | Derived dataset, keyed by model; rebuilt from the archive's images |

### Daily run record (replaces the log aggregation idea)

Record facts when they happen; don't mine or keep logs. Logs stay at 30 days.

- One item per office per local day, e.g. `PK=OFFICE#MKX`, `SK=DAY#2026-05-16`, written with one `UpdateItem` (`ADD`) per run
- Fields: `runs`, `nws_failures`, `stories_seen`, `rejected`, and a **96-slot failure bitmap** (one bit per 15-minute run slot, set when that run's NWS list failed)
- Outages = runs of consecutive set bits, with exact start and end times. Tiny: a few KB per office per year
- Best effort: a failed write logs a WARNING and never fails the run or blocks posting (it's not a step in `backend/side-effect-order`'s safety chain)
- Open: key the day by UTC or local time? Local matches how people talk about days; UTC keeps slots unambiguous at DST changes. Leaning toward UTC slots, converted to local at build time

## Pipeline

```
archive (S3) + ledger + daily run records (DynamoDB) + external weather data
        -> scripts/build_analytics.py        derived facts dataset (Parquet under analytics/)
        -> scripts/label_stories.py          Bedrock labels, cached (derived, re-runnable)
        -> scripts/build_year_review.py      facts JSON -> narrative (Bedrock) -> checked -> PDF
        -> publish step                      Telegram message per office (a new side effect)
```

- Every stage is re-runnable and writes only derived data until the final publish
- Dry run by default, `--apply` to write, and a separate explicit step to publish (same pattern as the migration scripts; the dev CLI never publishes)

## Inference (Bedrock)

- **Labels:** a small, fast model (Haiku 4.5 class) over each archived revision's image + text. Store the output with `model_id`, `prompt_version` and `labeled_at`. Re-label when either changes
- **Embeddings:** a multimodal embedding model over each archived image, for design flair's
  per-office distance. A different pattern from invoking a chat model (vectors plus a
  nearest-neighbour check, no prompt), and a useful one to learn for cloud model management.
  Compare with a perceptual-hash baseline before paying for it. Check which Bedrock embedding
  models accept images in `us-east-2`, and their prices, at spec time
- **Narrative:** a stronger model (Sonnet 5 / Opus 5 class) gets the **computed facts JSON as its only data**. It never counts or dates anything itself
- **Grounding check (deterministic):** every number, date, office and story title in the generated text must appear in the facts JSON, or the build fails. Invented facts in something shared with an NWS office aren't acceptable
- Inferred facts are marked as inferred in the PDF ("our AI reader thought...")
- Check Bedrock model access in `us-east-2` and prices before speccing (look them up, don't rely on memory)

### Model access in us-east-2, checked 2026-09-20

`aws bedrock list-foundation-models --by-provider anthropic`, all **ACTIVE**:

| Model id | Use | Modalities |
|---|---|---|
| `anthropic.claude-haiku-4-5-20251001-v1:0` | labels | TEXT + **IMAGE** in, TEXT out |
| `anthropic.claude-sonnet-5` | narrative | TEXT + IMAGE in, TEXT out |
| `anthropic.claude-opus-5` | narrative (stronger) | TEXT + IMAGE in, TEXT out |

- Haiku 4.5 accepts image input, which the labeling tier needs — confirmed, not assumed.
- `us.` and `global.` inference profiles exist for both Haiku 4.5 and Sonnet 5. Invoke the
  profile, not the bare model id.
- Sonnet 4 and Opus 4.1 are **LEGACY** in this region. Don't build on them.
- **Prices still unverified.** The Price List API (`aws pricing`) only exposes up to Claude 3
  Haiku/Sonnet for Bedrock, so it can't answer this. Use the Bedrock pricing page at spec time.

## The PDF infographic

- **Look:** inspired by the Weather Story graphic style (bold headline banner, big numbers, simple icons, map-like office context)
- **Branding caution:** don't use the NWS or NOAA logos or seal, or anything that makes it look like an official NWS product. Label it clearly as an unofficial, fan-made review. The data is public, but the product must not imply it's endorsed. This also matters for sharing with offices
- **Rendering:** HTML/CSS template -> PDF in the build script (e.g. WeasyPrint or headless Chromium); run locally or in CI, not in the posting Lambda. Charts follow one consistent palette
- **Per office:** one template, office data injected; MKX first
- **Delivery options (open):**
  - Attach with Telegram `sendDocument` (simple; bots can upload files up to 50 MB)
  - Or host it (S3 behind CloudFront or a presigned link) and post a link (needs a hosting and retention decision)
- Publishing is a new side effect: it needs its own place in `backend/side-effect-order` (render -> archive the PDF -> send -> record in the ledger) and a guard against double posting

## Tone guardrails

- Celebrate, don't rank. "Your busiest week" is good; cross-office leaderboards of mistakes are not
- Never try to identify individual forecasters, even if names or initials appear in an image. Say "the overnight shift", not people
- Typos and fixes are framed as care ("caught and fixed in 4 minutes")
- Machinery facts are a sidebar, not the headline

## Timeline caveat

- The bot went live on 2026-09-13, and the NWS API only lists **active** stories (no history). The 2026 edition is **"Season One: September to December"**
- A full-year 2027 edition needs the ledger, first/last seen and the daily run records recording **well before 2027-01-01**. Start recording is the most time-sensitive item here

## Open questions

- PDF attached vs hosted link?
- When to publish: late December, New Year's Day, or at the end of the season?
- Should inferred facts appear at all in a copy shared with an NWS office, or only in the channel version?
- Which external weather sources are acceptable (terms, reliability)?
- Is a mid-year "Season So Far" useful as a dry run of the pipeline (e.g. end of 2026 for MKX)?
