# ATLAS cloud daily intake

Files are prepared, not deployed by this worker. Parent applies migration.sql, deploys index.ts + core.mjs with verify_jwt=false (one-time database nonce authentication is implemented), configures ATLAS_OPENAI_API_KEY, then executes `select atlas_private.enqueue_daily_intake(true)` once and checks `atlas_private.daily_runs` / feed readback. Only activate schedule.sql after a successful run. No key is embedded in source.

Missing key, OpenAI billing/access failure, incomplete JSON or unexpected response is a logged failed run, not fabricated success. Zero candidates is valid. Each candidate's official company source must be web-search cited, fetched over HTTPS and include the model's quoted location excerpt. Evidence remains Pending and all human qualification booleans remain false. This is a limited automated source check, not independent verification of company facts or sales intent.

The date-keyed queue rejects repeated dispatches, each nonce expires in ten minutes and can be claimed once, and batch persistence locks the latest owner workspace before merging. Existing plans/reviews are retained. Before first owner sign-in, intake updates the private bootstrap seed; afterward it updates the authenticated owner's live workspace. Two UTC schedule times plus a named-zone local-hour check preserve 7 AM Eastern.

Run local tests: `node test-core.mjs`. Live SQL, Edge runtime, and OpenAI integration must be tested by the parent after deployment; these local tests do not establish those behaviors.

Official API references checked November 11, 2026:
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/models/gpt-5-mini
