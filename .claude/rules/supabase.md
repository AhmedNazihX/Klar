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
- Corpus tables are server-only: RLS on with no policies, and no grants to `anon` or `authenticated` on tables, sequences or functions.
- Vectors: an untyped `vector` column with `model`, `dims` and `content_sha256` on each row. Each (model, dims) arm gets its own partial HNSW cosine index on a cast, for example `(embedding::vector(1536)) where model = '…' and dims = 1536`. A query must use the same cast and predicate to hit the index, and should `set local hnsw.iterative_scan = relaxed_order`, because filters are applied after the index scan. Versions, `as_of` and reloads follow `docs/decisions/009-corpus-versioning.md`.
- Check that the new migration applies cleanly to the local database before calling it done. Don't use `supabase db reset` for this: it wipes the corpus every worktree shares (CLAUDE.md › Project rules for parallel work).
