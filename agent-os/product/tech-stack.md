# Tech Stack

## Frontend

N/A. Telegram is the interface: stories are posted to a Telegram channel through the Telegram Bot API.

## Backend

- **Language:** Python
- **Compute:** AWS Lambda, run on a schedule to check for new Weather Stories

## Database

- **AWS DynamoDB:** Durable state that records which stories have been posted, so none are posted twice

## Other

- **AWS S3:** Archive of Weather Stories (for the Phase 2 story archive)
- **Telegram Bot API:** Delivers the notifications and shows the stories
- **NWS Weather Stories:** Where the stories come from (MKX office for the MVP)
