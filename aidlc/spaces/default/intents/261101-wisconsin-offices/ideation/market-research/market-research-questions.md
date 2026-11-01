# Market Research & Competitive Analysis: Questions

## Sources

- [desc] Initial description: "Expand NWS office coverage to all NWS offices covering Wisconsin counties.  GRB,ARX,MPX,DLH  Each office gets a single production Telegram channel.  MPX is added to the existing staging channel to test multi-office behavior without cluttering it.  Staging channel will need to be renamed so it's not MKX-specific.  Avatars will need to be generated.  A pinned message with office information should be added to channels.  Telegram channel provisioning should be automated and a directory of channels stored persistently to keep track.  Cost should be a consideration, as this is a hobby project."
- [scope] Workflow-selected scope: `feature`.
- Upstream: `ideation/intent-capture/intent-statement.md` (approved): public channels from day one, identity written for strangers, fully automated provisioning including channel creation, README links as the only publishing, $20 a month total AWS ceiling.
- Research (2026-11-01):
  - NWS Bot on top.gg, a Discord bot that shows NWS products including office Weather Stories: https://top.gg/bot/823980769961050162
  - NWS Duluth home page, linking its Weather Story and its X and Facebook accounts: https://weather.gov/dlh
  - Telegram client configuration (`channels_public_limit_default` 10, `channels_public_limit_premium` 20): https://core.telegram.org/api/config
  - Telegram API Terms of Service: https://core.telegram.org/api/terms
  - Telethon FAQ on account bans with third-party clients: https://telethon.readthedocs.io/en/v2/developing/faq.html
  - NWS disclaimer (public domain, trademark, no implied endorsement): https://www.weather.gov/disclaimer
  - IFTTT RSS-to-Telegram applet: https://ifttt.com/applets/A5GkrBZy-send-new-rss-earthquake-alerts-to-telegram

## Q1. [Product owner] Why would a stranger follow one of these channels instead of what already exists?

Each office already shows its Weather Story on weather.gov and posts graphics on its own X and Facebook accounts, and a Discord bot shows Weather Stories on request. No Telegram feed of Weather Stories turned up. This sets what the channel description and pinned message promise.

A. Delivery: a phone notification for each new story, in an app they already use, with no social account or feed algorithm in the way
B. Delivery plus tidiness: a changed story replaces the old post, so the channel only ever shows current stories
C. A and B, plus focus: one office per channel with nothing else in it (no ads, no unrelated posts)
D. Not yet defined
X. Other (please specify)

[Answer]:

## Q2. [Product owner] How should posts notify readers who are strangers?

Today every new story and every update notifies, because the mission says updates should get your attention. Strangers may find update notifications noisy and mute the channel. Telegram lets a channel post silently.

A. Same as today: every new story and every update notifies
B. New stories notify; updates post silently
C. Same as today, but nothing notifies overnight in the office's time zone
D. Not yet defined
X. Other (please specify)

[Answer]:

## Q3. [Product owner] What can a reader do in a channel besides read?

Telegram channels can be read-only, allow emoji reactions, or link a discussion group for comments. Anything beyond reading means someone has to moderate it.

A. Read only: no reactions, no comments
B. Reactions only
C. Reactions plus comments in a linked discussion group
D. Not yet defined
X. Other (please specify)

[Answer]:

## Q4. [Product owner] What should each channel be called?

The NWS disclaimer says the NWS name may not be used in a way that implies endorsement or affiliation, so a name like "NWS Green Bay" is out. The MKX channel's avatar today is titled "MKX Weather Stories".

A. City first, marked unofficial, e.g. "Green Bay Weather Stories (unofficial)"
B. Office code first, e.g. "GRB Weather Stories", with "unofficial" in the description only
C. Region first, e.g. "Northeast Wisconsin Weather Stories"
D. Not yet defined
X. Other (please specify)

[Answer]:

## Q5. [Product owner] How should the four new avatars be made?

The description says avatars need to be generated. The MKX channel's avatar is an SVG in `assets/telegram/`. Avatars must carry no NWS or NOAA logo or seal.

A. From the MKX design as a template, changing each office's label (and colour, if useful)
B. A new design per office, made with an image-generation model
C. Designed by hand per office
D. Not yet defined
X. Other (please specify)

[Answer]:

## Q6. [Product owner] Does the existing MKX channel get the same identity as the four new ones?

The intent covers the four new channels and the staging channel's rename. The MKX channel was set up when it was only for you.

A. Yes: MKX gets the same naming, avatar style, description and pinned message as the new channels
B. Only the pinned message and description; its name and avatar stay
C. No: leave MKX as it is
D. Not yet defined
X. Other (please specify)

[Answer]:
