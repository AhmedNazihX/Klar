# AE.AFA.CAP.1

## Database

Development, tests, benchmark runs and the app all use one hosted Supabase project (Free plan,
Frankfurt `eu-central-1`; decision 034). No local Supabase stack is needed.

- `backend/.env` (from `backend/.env.example`): `DATABASE_URL` is the session pooler's connection
  string, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` the project URL and secret key.
- `frontend/.env.local` (from `frontend/.env.example`): `VITE_SUPABASE_URL` and the publishable key
  in `VITE_SUPABASE_ANON_KEY`.
- Schema changes: `supabase migration new <name>`, then `supabase db push` to the linked project
  (`supabase login` and `supabase link --project-ref <ref>` once). `supabase config push` applies
  `supabase/config.toml`'s auth settings (anonymous sign-ins on).
- Never reset the hosted database or drop its schema: every worktree shares its corpus.
- CI is unaffected: it starts its own throwaway local Postgres with the repo's migrations.
