# Tech Stack

## Frontend

N/A. Telegram is the interface: stories are posted to a Telegram channel through the Telegram Bot API.

## Backend

- **Language:** Python
- **Compute:** AWS Lambda, run on a schedule to check for new Weather Stories

## Database

- **AWS DynamoDB:** Durable state that records which stories have been posted, so none are posted twice

## Other

- **AWS S3:** Archive of Weather Stories (and the source for the Phase 3 Year in Review)
- **Telegram Bot API:** Delivers the notifications and shows the stories
- **NWS Weather Stories:** Where the stories come from (MKX office for the MVP)
- **AWS CloudWatch Alarms:** Watch the Lambda for errors and missed scheduled runs. A log metric filter counts posted stories, which catches the bot going quiet or reposting in a loop
- **AWS Budgets:** Emails me if monthly spend goes over a small limit
- **Infracost:** Estimates the monthly cost of the Terraform in `infra/` when I run `make cost`
- **AWS SNS:** Sends alarm notifications to my email address (the email subscription must be confirmed once)
