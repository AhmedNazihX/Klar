---
paths:
  - "supabase/**"
  - "**/*.sql"
---

# Rules for Supabase and SQL

- Load the `supabase-postgres-best-practices` and `supabase` skills before writing SQL.
- Create migrations only with `supabase migration new <name>`, so names are timestamped. Never edit a migration that is already merged to main; add a new one.
- Only one story at a time may change the schema (CLAUDE.md › Parallel work). All worktrees share one local database, so tests isolate themselves (a transaction per test, or a per-story schema).
- Every table holding user data has RLS enabled, with policies keyed on `auth.uid()`, and an RLS test showing that user A cannot read user B's rows.
- Vectors: `vector(1536)` with an HNSW cosine index. Record the embedding model and dimensions on each row.
- Check that `supabase db reset` applies cleanly before calling a migration done.
