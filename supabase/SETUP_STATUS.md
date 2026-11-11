# Supabase setup status — November 11, 2026

## Deployed

- Organization: BLorton22. Dedicated project: ATLAS (`iikworeqzzinccrhshed`, US East).
- Private starting snapshot: 29 companies, four qualification reviews, five intelligence signals. Canonical local account plans were empty at migration; browser-only interview edits were not imported.
- Owner-only workspace, first verified-email enrollment and versioned save RPCs. Only Brendan's personal email has a seed. No service-role secret in browser code.
- Owner sign-in: https://atlas-sales-demo-brendan.bluefir512.chatgpt.site/pipeline-login.html
- Public demo remains separate; visitor edits stay local.
- Daily intake Edge Function deployed with one-use expiring job authorization. It uses OpenAI web search, bounded company discovery, cited primary-source checks, deduplication and Needs review defaults. It preserves human plans/reviews and logs failures.
- Cron job `atlas-daily-sales-7am-eastern` exists but is PAUSED. UTC 11/12 invocations plus an America/New_York guard select 7 AM through DST.

## Verified

- SQL integration assertions for owner access, anonymous/other-user denial, stale versions and initialization passed in a rolled-back fixture transaction.
- Private transport tests passed: remote persistence, independent session reads, conflicts, network errors, refresh and public-demo isolation. Research validation tests passed.
- Live database readback confirms 29 companies, five signals and all existing reviews preserved.
- Live private URL redirects unauthenticated visitors to sign-in.
- A real worker invocation failed clearly with `ATLAS_OPENAI_API_KEY is not configured`; failure was persisted. No claim of successful company discovery is made.
- Supabase advisors flag the intentionally callable security-definer RPCs and private default-deny tables. RPCs check authenticated owner identity; worker RPCs are service-role-only, have empty search paths, and anonymous execution is revoked.

## Remaining activation

1. Owner adds `ATLAS_OPENAI_API_KEY` in Supabase Edge Function Secrets. Keep the value out of chat, GitHub and files.
2. Invoke `select atlas_private.enqueue_daily_intake(true);` as administrator. Read `atlas_private.daily_runs` and feed afterwards. A failed date can be explicitly retried; a running/completed date cannot be duplicated.
3. On verified successful completion, activate the existing cron job with `cron.alter_job` and deactivate the old Codex desktop automation through its automation tool. Do not silently run two independent pipelines.
4. Owner completes first email sign-in; verify an account save on a second device. Default email links can be pasted into the sign-in page's fallback if redirect configuration has not yet been customized.

End-to-end real-email sign-in, successful OpenAI intake and schedule activation remain pending. The local SQLite app remains a preserved historical workspace; after cutover, cloud state is authoritative. Never republish private state into the public demo.

## API key verification — November 11, 2026
The secret is now configured. A live retry returned OpenAI error 429 credit_balance_exhausted. API credits must be added before another retry. Cron remains paused; no new prospects were added. Error diagnostics now retain the sanitized provider error code without exposing the secret.

