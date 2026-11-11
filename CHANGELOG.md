## Sales-dashboard update — 2026-11-10
The current product is an OpenAI sales dashboard. Prioritize manufacturing and defense-tech startups, while including other credible prospective clients. Seed through later stage is in scope; no Series D ceiling. Funding is optional context, not a qualification gate. Prospects show business need, OpenAI fit, workflow, buyer, next sales action and priority. Daily automation at 7 AM Eastern now adds sales prospects with these fields. Any earlier stage-limit or research-first descriptions below are superseded by CRITERIA.md and MEMORY.md. Existing records and account management are preserved. 31 automated tests passed and the sales homepage was verified in the browser.

# Changelog — 2026-11-10

- Consolidated on Pro Account Handoff. Retained all seven account workspace views, plans, stakeholders, opportunities, activities, CSV export and version conflicts.
- Added research-company intake, identity deduplication, structured evidence reviews and version-safe prospect promotion. Qualification requires human-reviewed US/sector/latest Seed–Series D evidence, sources, date, reviewer and rationale.
- Added daily feed, JSON intake/template, non-dollar signal types, source failure logs, event deduplication, and dated JSON/Markdown discovery reports.
- Added on-demand RSS collection with 72-hour overlap and per-source catch-up. Two live feeds parsed successfully; one Pending company match included. No schedule activated.
- Ported Phase 2 optional USAspending candidate search into the shared feed. Matches stay Pending; no revenue or qualified award claims are inferred.
- Retained Phase 2 company and event references separately as unverified migration material.
- Hardened localhost reads/writes and validation. Existing records stay in atlas_plans.sqlite, independent of research rebuilds.
- Added 30 automated tests and browser workflow/desktop/mobile verification. Fictitious test records excluded from delivered databases.

## Remaining limitations

- Human evidence review is still required; historic company funding stages have not been independently re-verified.
- Automatic discovery covers two configured RSS feeds. Other listed publishers, company/government announcements and primary verification remain manual. Feed retention limits catch-up coverage.
- New companies need identity intake; unmatched headlines are saved to discovery reports. Name matching and signal-type classification are heuristic.
- Existing feed events are immutable in this phase; a corrected duplicate batch is skipped rather than replacing an event. Keep corrections in the company review or account activity. No full event adjudication editor yet.
- No scheduler installed, no outreach, and no CRM/billing/PitchBook integrations. Customer labels and opportunity values are user-entered planning data.
- USAspending matching needs legal-name/UEI review and was tested offline, not against a live API response.
- Qualification does not auto-expire. Review dates are visible; re-review after later funding or ownership changes. Downgrading a review preserves CRM history.
# Qualification and federal sales update — 2026-11-10

- Added a dashboard discovery-gap table and editable buying-case fields for all accounts.
- Added Commercial / Federal / Partner sales motions, mission owner, funding path, acquisition path and deployment requirements.
- Preserved existing account data and qualification gates; notes are not verified buying intent.
- Validated 33 Python tests, browser adapter tests, and browser save/reload for the new fields.

