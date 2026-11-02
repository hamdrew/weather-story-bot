# Rough Mockups — Questions

Input: the approved intent statement, scope document and intent backlog. The only UI is the CloudWatch
dashboard (the owner is the only reader). These questions shape a rough sketch of it, not a design.

## Q1. [Design] What should the dashboard show at the very top?

The owner wants to tell in under a minute whether the bot is healthy, so the top of the page matters most.

A. A single clear healthy / not healthy answer, with the signals behind it just below
B. The key signals as a row of numbers and small trend lines, with no single verdict
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q2. [Design] How should warnings appear on the dashboard? (select all that apply)

Nothing notifies the owner, so the warnings area has to be easy to notice when looking.

A. A count of warnings by kind over a recent period
B. A list of the most recent warnings with their time (in America/Chicago) and kind
C. A trend of each warning kind over time
D. Not yet defined
X. Other (please specify)

[Answer]: A, B

## Q3. [Design] How is the dashboard organised?

A. One page, top to bottom: health first, then warnings, then detail
B. Health and warnings side by side on one page
C. Separate pages or tabs for health and for warnings
X. Other (please specify)

[Answer]: A

## Q4. [Design] Which devices must it work on?

A. Laptop or desktop browser only
B. Laptop or desktop, and readable on a phone
C. Not yet defined
X. Other (please specify)

[Answer]: B

## Q5. [Design] Are there accessibility or look-and-feel requirements?

CloudWatch dashboards come with their own look; this asks whether anything beyond that is needed.

A. No; the standard CloudWatch look is fine
B. Don't rely on colour alone to show a problem (for example add a word or symbol)
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q6. [Design] Can a warning or an error change the verdict at the top?

Asked after the review (R-02), once errors joined the dashboard.

A. Errors yes, warnings no; the verdict area also shows the total warning and error counts
B. Neither; the verdict area shows the total counts
C. Both can, by rules fixed in requirements
X. Other (please specify)

[Answer]: A

## Q7. [Design] What does the verdict say when there is no data (the bot should have run but nothing came in)?

Asked after the review (R-01).

A. Not healthy, naming "no data" as the signal that is off
B. A separate "unknown" state, clearly not "healthy"
X. Other (please specify)

[Answer]: B

## Q8. [Design] Does one dashboard cover one environment or both?

Asked after the review (R-03).

A. One dashboard per environment, so no environment label is needed on the page
B. One shared dashboard with both environments, labelled
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Top of the page: a single healthy / not healthy answer, with the signals behind it just below (Q1).
- Warnings: a count by kind over a recent period, and a list of the most recent warnings with time (America/Chicago) and kind (Q2).
- Layout: one page, top to bottom: health first, then warnings, then detail (Q3).
- Devices: computer, and readable at phone width (Q4).
- Look and feel: the standard CloudWatch look; no extra requirements (Q5).
- Errors change the verdict, warnings don't; the verdict area shows both totals (Q6).
- No data gives a separate "unknown" state, clearly not "healthy" (Q7).
- One dashboard per environment, with no environment label on the page (Q8).

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
