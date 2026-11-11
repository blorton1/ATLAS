## Sales-dashboard update — 2026-11-10
The current product is an OpenAI sales dashboard. Prioritize manufacturing and defense-tech startups, while including other credible prospective clients. Seed through later stage is in scope; no Series D ceiling. Funding is optional context, not a qualification gate. Prospects show business need, OpenAI fit, workflow, buyer, next sales action and priority. Daily automation at 7 AM Eastern now adds sales prospects with these fields. Any earlier stage-limit or research-first descriptions below are superseded by CRITERIA.md and MEMORY.md. Existing records and account management are preserved. 31 automated tests passed and the sales homepage was verified in the browser.

# Continue ATLAS — Consolidated build, 2026-11-10

Start with README.md, CRITERIA.md and DAILY_SOURCES.md. Pro Account Handoff is the main application. The old Phase2 update-only server must not overwrite atlas_server.py.

ATLAS is Brendan's independent OpenAI Federal Account Director interview workspace, unrelated to Long River or acquisitions. Target US Seed–Series D defense tech, advanced manufacturing and American Dynamism companies. Public facts, source-review attestations and commercial planning hypotheses must remain distinct. Tracking or promotion never proves an OpenAI customer relationship.

## Current implementation

- Existing seven-view account workspace and separate persistent account plan store preserved.
- research.html: qualification queue, candidate intake, source/reviewer/date/rationale review, gated promotion, feed/import and on-demand daily intake.
- research_store.py: independent research tables in atlas_plans.sqlite, optimistic review conflicts, atomic CRM-preserving promotion, candidate identity deduplication, event/run persistence.
- daily_intelligence.py: RSS/Atom title discovery, per-source overlap/catch-up, Pending known-company matches, unmatched headline reports, source failures. Two feeds configured; no automatic schedule.
- collect_awards.py: adapted Phase2 full-name USAspending candidate search, all Pending. phase2_reference.json is reference-only, not verified data.
- atlas_server.py: existing API plus research endpoints. Defaults now match packaged atlas_market.sqlite and port 8766. Account dashboard links research workspace, refresh reloads research status and candidates, and legacy plan qualification cannot bypass evidence gate.

All research additions, reviews, events and CRM records persist independently of market-db rebuilds. Preserve/back up atlas_plans.sqlite. Included starter plans store contains real RSS intake only, no test plans/reviews/candidates. The original market DB is unchanged.

## Evidence and verification

30 automated tests passed; see VERIFICATION.md and verification/tests.txt. Browser checks exercised intake → qualification → promotion → CRM edits → reload, Pending/non-dollar import, duplicate handling, failure coverage, all seven navigation views, and mobile feed layout. Live RSS run parsed Breaking Defense and Defense One successfully; one match remains Pending. USAspending was validated with offline fixtures only. Existing research is not independently current-stage verified.

## Next priorities

1. Add event-level evidence correction/adjudication with history rather than silently changing imported events.
2. Expand validated publisher/primary-source adapters and expose unmatched discovery headlines in the UI, beyond saved reports.
3. Add configurable evidence freshness/review reminders; current qualification does not expire automatically.
4. Improve entity identity/alias/UEI matching. Add licensed PitchBook import only with authorized data.
5. Schedule daily research only if the user requests activation; currently on demand or CLI.

Read CHANGELOG.md limitations before claiming autonomous discovery, independently verified facts, real customer spend or complete contract coverage. No outreach or external deployment performed.
