# 034 · The shared database moves to a hosted Supabase project in Frankfurt

- **Date:** 2026-10-11
- **Story:** F11 (docs/BACKLOG.md); brings forward part of S3 (INIT › Tech stack, "Hosting (at deployment)")
- **Status:** accepted (user, 2026-10-11: option B)

## Question
Every worktree, the ~4,400 backend tests, the app and the benchmark runs use one Supabase stack running in Docker
on the user's machine, and the load on that machine is high. Should development move to a hosted Supabase project
in the EU now, instead of only at deployment (S3), and if so as the only database or next to the local one?

## Options
| Option | What was compared or measured | Result | Source |
| --- | --- | --- | --- |
| A. Add a hosted EU project, keep local for development | Machine load; test speed; data location | Load unchanged: the local stack keeps running. Tests stay fast. Users' data in the EU at deployment | Orchestrator's comparison, 2026-10-11 |
| **B. Switch everything to a hosted EU project** | Same | The local Docker stack is no longer needed. Every query crosses the network, so the DB tests get slower (not yet measured). One remote database shared by every worktree, as today | Same |
| Size to move | Local database size | 409 MB in total: `provision_embeddings` 336 MB, `provisions` 43 MB, `eval_case_results` 8.8 MB, `classifications` 6 MB | `pg_database_size` / `pg_total_relation_size` on `supabase_db_aiact`, 2026-10-11 |
| Schema to move | Migrations | 19 files in `supabase/migrations/` (pgvector, pg_cron purge, embedding-arm indexes) | `ls supabase/migrations` |
| Supabase plan | Free vs Pro | Free: 500 MB database, paused after 7 idle days, so too small and unreliable for 409 MB. Pro: $25/month, 8 GB included | Supabase pricing page, as the orchestrator knows it; **to confirm when creating the project** |
| OpenRouter cost | Re-embedding vs copying | $0: the corpus rows and their embeddings are copied, not recomputed | — |
| CI | `.github/workflows/ci.yml` | Unaffected: CI starts its own throwaway local Postgres with the repo's migrations | `ci.yml` lines 51–60, 146–166 |

## Decision
B: a hosted Supabase project in Frankfurt (`eu-central-1`) becomes the one database for development, tests,
benchmark runs and the app. The user chose it on 2026-10-11 because the local stack's load on their machine is too
high, and confirmed it on 2026-10-11 after the measurement below, because the goal is a deployment-ready setup:
the database the app will run on in production is the one developed and tested against. The slower tests are an
accepted cost.

Measured 2026-10-11 (`ps`, `docker stats`, `sysctl vm.swapusage`): the CPU load (load average 16–19 on 12 cores)
came mostly from two story workers' test runs; the whole local Supabase stack used ~0.35 core and ~3.1 GB RAM
(mostly Studio and Analytics); swap was 39.9 of 40 GB full. So the move frees memory more than CPU. A cheaper
alternative, starting only the needed local services (`supabase start -x …`), was offered and declined in favour
of deployment readiness.

## Consequences
- **Order:** F11 does the move. It holds `Resource: db-schema`, so it starts after V8's current work frees the
  resource. V8's paid runs then store their results in the hosted project.
- **User part:** create the project (Pro plan, region Frankfurt) and put its URL, keys and connection string in
  `backend/.env` and `frontend/.env.local`. These are never committed, and the agent never creates or bills an
  account.
- **Agent part:** link the project and push the 19 migrations. Copy the corpus, obligations and other data rows
  from local (data only, no re-embedding). Apply `supabase/config.toml`'s auth settings to the hosted project
  (S3's P3 note). Check that the connection pooler accepts the tests' `PGOPTIONS='-c lock_timeout=15s'` (F9's
  note); otherwise use the session pooler or direct connection that does. Measure the backend test suite's time
  before and after. Update CLAUDE.md (`supabase start`, *Database is shared*) and the READMEs.
- **Unchanged:** CI keeps its local throwaway database. "Never `supabase db reset`" still holds, and on the hosted
  project the equivalent is never resetting or dropping the shared schema.
- **Privacy:** P12's "Stored in <region>" line and P17's `[REGION]` placeholder can now say Frankfurt (EU); S3
  still decides the API and frontend hosts.
- **Revisit if** the test suite becomes too slow to run per story (for example several times slower than local),
  if the remote database becomes a bottleneck for parallel worktrees, or if Pro's cost is a problem: then go back
  to A, or run local Postgres only (`supabase start -x …`, as CI does) for the tests.
