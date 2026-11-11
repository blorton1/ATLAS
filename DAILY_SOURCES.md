## Sales-dashboard update — 2026-11-10
The current product is an OpenAI sales dashboard. Prioritize manufacturing and defense-tech startups, while including other credible prospective clients. Seed through later stage is in scope; no Series D ceiling. Funding is optional context, not a qualification gate. Prospects show business need, OpenAI fit, workflow, buyer, next sales action and priority. Daily automation at 7 AM Eastern now adds sales prospects with these fields. Any earlier stage-limit or research-first descriptions below are superseded by CRITERIA.md and MEMORY.md. Existing records and account management are preserved. 31 automated tests passed and the sales homepage was verified in the browser.

# ATLAS daily discovery sources

Scope is OpenAI sales research in US defense technology and manufacturing. Follow ATLAS_CONTEXT.md in the workspace and the user's latest criteria.

| Source | Entry point | Intended signal |
| --- | --- | --- |
| a16z American Dynamism | https://a16z.com/category/american-dynamism/ | Investment announcements and company discovery |
| a16z portfolio | https://a16z.com/american-dynamism/ | Company universe, with monthly portfolio updates |
| Khosla Ventures | https://www.khoslaventures.com/ | Portfolio companies and investment announcements |
| Axios Technology | https://www.axios.com/technology | Financing, industrial technology and business news |
| Manufacturing Dive | https://www.manufacturingdive.com/ | Plant openings, expansions, manufacturing technology and hiring |
| Breaking Defense | https://breakingdefense.com/ | Defense business, technology and contract developments |
| Defense News | https://www.defensenews.com/ | Defense industry and procurement discovery |
| Defense One | https://www.defenseone.com/ | Defense technology and industry discovery |
| IndustryWeek | https://www.industryweek.com/ | Manufacturing operations and technology adoption |
| Company newsrooms | Source URLs in market_seed.psv | Primary confirmation of financing, expansion and contracts |
| Government contract announcements | https://www.war.gov/News/Contracts/ | Award values, modifications, ceilings and obligations |
| DIU | https://www.diu.mil/latest | Prototype and production awards |
| SEC EDGAR | https://www.sec.gov/edgar/search/ | Filing-based entity and financing checks |

Checked entry pages for a16z, Khosla, Axios, Manufacturing Dive and Breaking Defense on 2026-11-10. Other entries are research candidates and should be checked during each run. These are website discovery entry points, not claims of installed RSS or API connectors.

## Daily procedure

Search the prior 72 hours with overlap to catch delayed indexing. After an outage, resume from the last successful review date. Record publication date separately from collection date. Deduplicate canonical URLs and company/event/date combinations. Keep every discovered event in a dated report even when the dashboard displays only one headline event per company.

Use investor and trade coverage to discover accounts, then follow to primary company or government confirmation. Label secondary-only claims as pending. A portfolio listing alone does not establish a new funding round. Log unavailable or paywalled sources explicitly.

Save dated research reports under daily_updates. For each event include company, US-presence evidence, category, event/publication dates, source URL, amount and amount basis when disclosed, verification status, and a brief sales-workflow hypothesis. Avoid copying full articles.

The consolidated research intake accepts funding, contract, hiring, expansion, ai_adoption, partnership and product_launch events, including null amounts. Use research.html or daily_intelligence.py; the legacy PSV seed importer remains for historical rebuilds only. Preserve the seed. Company-name RSS and USAspending matches remain Pending until human review. Do not invent amounts.

## Confirmed targeting

Apply CRITERIA.md for all daily discovery. Seed through Series D, US defense technology, advanced manufacturing and American Dynamism companies are the qualified universe. Verify latest disclosed stage. Existing records need re-screening before they are labeled qualified under this updated scope.


## Consolidated build — 2026-11-10

On-demand RSS adapters are configured in daily_feeds.json for Breaking Defense and Defense One. Both parsed successfully in a live check on 2026-11-10. Other entry points above are manual discovery sources, not installed collectors. Check daily sources or run daily_intelligence.py; no background scheduler is installed. Dated reports retain unmatched headlines and source failures. RSS retention limits historical catch-up. Customer spend remains unknown. See README.md for batch schema and optional USAspending collection.
