# AE.AFA.CAP.1

## Database

Two databases (decision 034 and its amendment):

- **Hosted** (Supabase Free plan, Frankfurt `eu-central-1`): the app, the benchmark runs and their
  stored results.
  - `backend/.env` (from `backend/.env.example`): `DATABASE_URL` is the session pooler's
    connection string with `?sslmode=require`, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` the
    project URL and secret key. Turn on the dashboard's Database settings > SSL Configuration >
    "Enforce SSL on incoming connections".
  - `frontend/.env.local` (from `frontend/.env.example`): `VITE_SUPABASE_URL` and the publishable
    key in `VITE_SUPABASE_ANON_KEY`.
- **Local** (the Supabase CLI's Postgres on `127.0.0.1:54322`): the backend tests, every worktree
  sharing it, as CI does. `make db` starts it slim, Postgres only:
  `supabase start -x gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor`.
  The tests use `TEST_DATABASE_URL` (default: that database) and never follow `DATABASE_URL`.

Schema changes: `supabase migration new <name>`, then apply it to both, `supabase migration up
--local` and `supabase db push` to the linked project (`supabase login` and `supabase link
--project-ref <ref>` once). `supabase config push` applies `supabase/config.toml`'s auth settings
(anonymous sign-ins on) to the hosted project. Never reset either database or drop its schema:
the corpus in each is shared.
