# ATLAS — Sales Prospecting & Account Dashboard

An interview portfolio prototype by Brendan Lorton: identify potential OpenAI customers, turn public signals into sales hypotheses, qualify prospects, and manage account next steps.

**[Try the live interview demo](https://atlas-sales-demo-brendan.bluefir512.chatgpt.site)** — no download or login. Explore all 29 companies, edit account plans, assess prospects and view intelligence. Demo edits stay in each visitor's browser; use Reset demo to restore the starting snapshot. The public demo is a November 10 snapshot, refreshed by republishing, rather than a shared live CRM.

**Included example data:** 29 companies as of November 10, 2026, including four newly added prospects: Nominal, Machina Labs, Neros Technologies, and Onebrief. Both SQLite databases and sales briefs are intentionally included. This is an independent demonstration, not an official OpenAI product or a list of confirmed OpenAI customers.

## Run locally

Requires Python 3.10 or newer. No third-party packages or API key required for the dashboard.

```sh
git clone https://github.com/blorton1/ATLAS.git
cd ATLAS
python atlas_server.py
```

On Windows, `py atlas_server.py` or `./Start_ATLAS.ps1` also works.
Open **http://127.0.0.1:8766/atlas_growth_live.html**. Keep the server terminal open. For another port use `python atlas_server.py --port 8767`.

## Five-minute interview demo

The sales dashboard now includes **Qualification gaps** for featured prospects. Open **Build buying case** to record a value baseline, evaluation target, economic buyer, champion, compelling event, decision process and competitive advantage. Select Commercial, Federal or Partner as the sales motion. Federal / partner fields capture the mission owner, funding path, acquisition route and deployment requirements. Blank inputs remain visible as discovery gaps; entered notes are not independently verified or used as automatic promotion gates.

1. **Prioritize:** inspect company cards, business needs, buyer roles and next sales steps.
2. **Go deep:** open Nominal. Separate its sourced funding signal from the hypothesis that OpenAI could support engineering AI workflows. Discuss the current model stack, deployment constraints and evaluation criteria you would qualify.
3. **Qualify:** inspect a prospect's evidence and review status. New additions remain **Needs review** until human qualification. Seed through later-stage companies are in scope; funding stage is context, not an exclusion gate.
4. **Manage:** demonstrate account plans, opportunities, contacts and activity tracking. Promotion preserves existing account history and never establishes customer status.
5. **Explain the daily workflow:** review dated intelligence and sales briefs in `daily_updates/`. Evaluate results by qualified meetings, useful evaluations and pipeline creation, rather than raw company counts.

## Daily intelligence and automation

```sh
python daily_intelligence.py
```

The built-in collector checks configured RSS feeds with a 72-hour overlap, records source failures, and queues matched headlines for review. It does not independently deliver the full web prospecting workflow. The November 10 sales run used an agent-assisted web review to add four companies and four supporting events.

The owner's Codex automation is configured separately for 7 AM Eastern. **Cloning this repository does not install that schedule or transfer access to Codex.** See `AUTOMATION.md` for the workflow and `DAILY_SOURCES.md` for source coverage. A scheduled run requires the relevant execution environment and internet access.

## Included data and boundaries

- `atlas_market.sqlite` and `market_seed.psv`: 25 original example company records; historical claims require current review.
- `atlas_plans.sqlite`: current prospect additions, qualification records, intelligence feed and account-management store.
- `daily_updates/`: dated source evidence and sales hypotheses, with freshness and coverage limitations.
- No confirmed buying intent, budgets or existing OpenAI relationships are implied. Disclosed financing is not revenue or prospective OpenAI spend. Neros financing is conditional.
- This is a local, single-user prototype, not a production multi-user CRM. No licensed PitchBook, internal OpenAI CRM or billing integration is included. Do not expose the local server directly to the internet.
- Future database edits are local changes; they are not automatically published to GitHub. Back up the databases before replacing them.

## Test

```sh
python -m unittest discover -v
```

Tests use disposable stores. The latest prospecting run verified 29 projected accounts, four new candidates and supporting events, with existing account plans and reviews preserved.

## Project files

`atlas_server.py` serves the dashboard and API; `account_plan_store.py` stores CRM records; `research_store.py` handles prospect intake, qualification and intelligence; `atlas_growth_live.html` is the sales dashboard; `research.html` provides evidence review and daily feed. Some internal names retain the earlier research terminology.

See `CRITERIA.md` for current sales criteria and `CHANGELOG.md` for development history. Older handoff and verification documents are historical; this README and current criteria describe the interview version.

## Build the browser demo

Run `python demo/export_demo.py /path/to/output/dist` to export the current databases with the browser adapter. Serve that directory with any static HTTPS host. `node demo/test-demo-api.cjs` checks isolated persistence, qualification, promotion, duplicate prevention and storage errors. The local Python app remains the canonical account-management workspace; visitor edits never write to its databases.

