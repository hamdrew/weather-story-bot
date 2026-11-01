# Product Mission

## Problem

National Weather Service (NWS) Weather Stories are great, but you have to remember to go to the NWS website to see them. They are also hard to view on that site from an iPhone.

## Target Users

Just me. This is a personal tool.

## Solution

Two things:

- **Automatic delivery:** New Weather Stories are found automatically and pushed to my phone, so I don't have to remember to check.
- **Easy to read on a phone:** Each story's graphic and description are shown in Telegram, which looks good on an iPhone.

## Principles

- **Don't trust the NWS API.** It has re-issued stories under new image IDs, with `updateTime` set to 1970, and sent duplicates. When it's unclear which story is which, the bot posts nothing for those stories, ignores them, and emails me. A wrong or duplicate story in Telegram is worse than a short delay while NWS fixes its data.
- **Updates should get my attention.** A changed story is posted again as an update, so I get a notification, and the old message is removed.
