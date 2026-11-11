## Sales-dashboard update — 2026-11-10
The current product is an OpenAI sales dashboard. Prioritize manufacturing and defense-tech startups, while including other credible prospective clients. Seed through later stage is in scope; no Series D ceiling. Funding is optional context, not a qualification gate. Prospects show business need, OpenAI fit, workflow, buyer, next sales action and priority. Daily automation at 7 AM Eastern now adds sales prospects with these fields. Any earlier stage-limit or research-first descriptions below are superseded by CRITERIA.md and MEMORY.md. Existing records and account management are preserved. 31 automated tests passed and the sales homepage was verified in the browser.

# ATLAS verification — 2026-11-10

## Automated checks

30 tests passed under Python 3.12.14. Full output: verification/tests.txt.

- Evidence requirements, unsupported/out-of-stage decisions, URL/date validation, review and plan version conflicts.
- Atomic promotion preserving an existing Partner relationship, sales stage, ownership, objectives, stakeholders, opportunities and activities.
- Candidate intake/deduplication and persistence independently of the unchanged market database.
- Real HTTP API exercise: all legacy reads, account saves, candidate intake, qualification, promotion, pending feed import/projection, duplicate repeat, invalid bodies, missing origin, and unexpected Host rejection.
- Atomic invalid-batch rejection, optional dollars/publication dates, URL/title deduplication, multiple events sharing a source, source failure logs and successful-run tracking.
- RSS/Atom parsing, pending matches, unmatched discovery queue, failure reports, repeat collection, bad config, overflow rejection without cursor advance, and separation of manual-import/RSS cursors.
- USAspending full-name query, pending-only amounts, unknown publication date, offline source failures, bounds, malformed results and integration with the real feed store. Live API not exercised.

## Browser workflow

Used a separate temporary plans database on port 8777; fictional data excluded from the ZIP databases.

1. Added ATLAS QA Test Company via the research form; observed 26 companies, Needs review and disabled promotion.
2. Saved a complete fictional test review; observed Qualified target and enabled promotion.
3. Promoted; observed managed count 1 and Prospect relationship.
4. Followed account profile link. Saved owner/objective/next action, fictional stakeholder, a $100,000 TEST ONLY pilot planning opportunity, and a research activity.
5. Reloaded. Owner, objective, next action, stakeholder/opportunity counts and activity persisted. Qualification audit activity remained visible.
6. Imported a non-dollar Pending hiring event with unknown publication date and a simulated failed source. Feed showed Pending, unknown publication date, partial run and failure detail. Repeat import showed 0 added / 1 duplicate.
7. Checked live source collection under restricted network access; failures appeared explicitly without false successful-run status.

## Live collection and clean release snapshot

An approved network-enabled CLI run parsed 15 dated Breaking Defense headlines and 22 Defense One headlines on 2026-11-10. It imported one company-name headline match as Pending and wrote dated JSON/Markdown reports with unmatched headlines. The release includes this public discovery snapshot, zero account plans, zero qualification reviews and zero intake/test companies.

Clean release store rendered on port 8778. All seven existing navigation views rendered, and Refresh records succeeded. Desktop and 390 × 844 mobile feed layouts visually checked; see verification/feed_desktop.png and feed_mobile.png. Viewport reset after testing. No browser was pointed at an existing user database.

## Boundaries

No claim was independently verified against its underlying primary article during this implementation. The live RSS headline remains Pending. Original 25 research companies are not automatically qualified. No background schedule, outreach, deployment, Git commit or change to the original Downloads archives was performed. Optional USAspending access was tested using fixtures only.

See README.md for safe retention of an existing atlas_plans.sqlite and CHANGELOG.md for remaining limitations.

## Archive release check

ZIP CRC check and both SQLite integrity checks passed. Original market database bytes match Pro Handoff. Exact archive extracted into a clean directory and its server started with default database arguments on test port 8789; both pages, bootstrap, health and research endpoints returned 200. Research returned 25 companies, one Pending feed event, no plans and no reviews. Launcher runtime detection passed on this machine (Python 3.12.14). No disposable test records are included in release databases.
