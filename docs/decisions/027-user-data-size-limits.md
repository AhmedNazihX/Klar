# 027 · User data: a 4 MB import cap and a per-user storage budget

- **Date:** 2026-10-01
- **Story:** P3b (docs/BACKLOG.md); affects P18/P19 (the Your data view) and S3 (deployment)
- **Status:** accepted (the user, 2026-10-01: option B with a 4 MB cap; and the fixed date floor below)

## Question
P3's `import_my_data` had a 5 MB cap, but a classification result may be up to 256 kB, so an account with about 20
maximum-size (or 170 typical) classifications could export a file it could not import again. P3b's first fix
dropped the cap, relying on Postgres's own limit of 268435455 bytes (255 MiB) on one jsonb value. The review then
found that a round trip near that size got the shared database's backend killed for running out of memory
whenever another test ran at the same time. The question was how large one import may be, and what happens to
an account whose export would be larger.

## Root cause
- `export_my_data` returns the whole account as **one jsonb document**, and `import_my_data` takes it back in one
  call. The document's size limit (255 MiB) is Postgres's; the memory one call needs is the host's.
- One import needs **about 20 times the document's size** in backend memory (measured below). The plpgsql loop
  copies the document's subtrees (`jsonb_array_elements`, `->`, `jsonb_to_recordset`) and holds them until the call ends.
- The `authenticated` role's 8 s `statement_timeout` does not help: a 64 MB import finishes in about 1 s, so memory
  runs out long before the timeout.
- With no cap, a few anonymous sessions importing large files at once can take the database down (a denial of
  service), and with it every user's session.

## Measurement
Method: one size at a time, each on a fresh connection, started only after `pg_stat_activity` showed no other client
for 15 s. Each call ran as PostgREST runs it: `set local role authenticated`, the JWT claims set,
`set local statement_timeout = '8s'`, the document sent as JSON text and cast to jsonb, then rolled back. Memory is
the backend's peak private memory (RssAnon, sampled inside the `supabase_db_aiact` container); the peak RSS with
shared buffers was 6 MiB higher every time. Results of 256 kB each unless noted. Local Supabase, 2026-10-01.

| Document | Peak backend memory | Duration | Within 8 s |
| --- | --- | --- | --- |
| 5 MB | +102 MiB | 0.11 s | yes |
| 10 MB | +199 MiB | 0.21 s | yes |
| 20 MB | +399 MiB | 0.36 s | yes |
| 20 MB (30 kB results) | +402 MiB | 0.44 s | yes |
| 40 MB | +799 MiB | 0.72 s | yes |
| 64 MB | +1279 MiB | 1.16 s | yes |

Memory grows linearly, about 20 MiB per MB, whatever the size of each result. At 255 MiB that is about 5 GB.

**Sizing:** the repo names no hosting target, so this assumes a **1 GB instance with 4 imports at once**. About
half the memory goes to shared buffers, the OS and the other connections, which leaves about 400–500 MiB, or
100–125 MiB per import: a document of 5–6 MB. The cap is set below that, at **4 MB** (about 80 MiB per import).

## Options
| Option | What it does | Cost | Result |
| --- | --- | --- | --- |
| A. Export refuses above the cap | `export_my_data` raises a clear error when the document is larger than 4 MB | About 10 lines of SQL, 2 cheap tests, a frontend message | The user can't take their data out until they delete some; the export itself still builds the whole document first |
| **B. Per-user storage budget** (chosen) | A trigger keeps each user's stored data within what one export can carry | About 40 lines of SQL, 5 cheap tests, a "storage full" message | Every genuine export imports; storage per anonymous user is bounded too |
| C. Export and import in parts | A new format version split by inventory or system, each part under the cap; a chunked import | About 100 lines of SQL, frontend work (several files or a zip), 6–8 tests | No quota, but the most code, and it touches P19 |
| D. Cut the ×20 overhead | Rewrite the import set-based to avoid the nested copies | Unknown: not measured, needs a spike | Could allow a larger cap; can be combined with any of the above |

## Decision
- **Import cap: 4 MB** (`4 * 1024 * 1024` bytes of the document's text). `import_my_data` rejects a larger file
  with SQLSTATE **PT413**, which PostgREST answers with HTTP 413.
- **Storage budget: the cap less 1 kB** (4193280 bytes) per user, across inventories, systems, classifications
  and interview answers. The 1 kB covers the export's envelope (format, version, exported_at; about 100 bytes).
  A write that would push the total past the budget fails with SQLSTATE **PT507** (HTTP 507, "storage full"),
  and the whole statement rolls back, so an import that doesn't fit adds nothing. A write that doesn't grow the
  data always passes, so an account over the budget can still shrink.
- **What counts:** a row's stored size is the bytes it adds to the export's text. That is the same object
  `export_my_data` builds for it (child arrays empty), plus 2 bytes for the separator, with `created_at` counted at
  its widest rendering (32 characters). This is the measure the import cap reads (`octet_length(data::text)`), so
  an account within the budget always exports at or under the cap. Counting `created_at` at its widest keeps the
  size independent of the time and the session's time zone, so a row always subtracts what it added.
- **How it's kept:** a running total per user in `private.storage_usage`, updated by an `after` row trigger
  (`private.track_storage()`) on the four tables. A sum over the user's rows on every write would read up to 4 MB
  per insert, and an import of n rows would read it n times.
- **Concurrency:** the trigger's upsert locks the user's `storage_usage` row until the transaction ends. A second
  writer for the same user waits, then re-reads the committed total and is checked against it. That row lock does
  the job of a per-user `pg_advisory_xact_lock`, so none is taken.
- **Resulting quota:** about **130 typical** (30 kB) or **15 maximum-size** (256 kB) classifications per user,
  with their systems and answers.

## Date floor (the same story)
`private.stamp_timestamps()` also rejects (SQLSTATE 22008) any `created_at` before **2026-09-28T00:00Z**, the day
the user-data schema went in, so `-infinity` or year 0001 can't break sorting, the export or date decoding. The
backlog suggested the owner's `auth.users.created_at` as the floor. The user chose a fixed date instead because an
import restores a file into a newer session (a new browser, or after the 30-day cleanup, decision 013): every date in
a real export is older than the new owner, and the import must keep its dates and order.

## Consequences
- **Where it lives:**
  - `supabase/migrations/20261001190510_user_data_size_limits.sql`: the cap, the budget, the trigger and the backfill.
  - `supabase/migrations/20261001182534_created_at_floor.sql`: the date floor.
  - `20261001181716_import_size_cap.sql` (which dropped the cap) is superseded.
  - The tests are in `backend/tests/db/test_user_data_schema.py`:
    - `IMPORT_MAX_BYTES` and `STORAGE_BUDGET`, with a boundary test at and over the cap.
    - A full-budget round trip, the budget and delete tests, and an import past the budget.
    - A two-connection race.
- **Changing the cap** means editing `max_bytes` in `import_my_data`, `budget` in `private.track_storage()` and the
  two test constants together; the round-trip test fails if the budget no longer fits the cap.
- **Keep the measure in step:** `private.export_bytes()` mirrors the objects `export_my_data()` builds. If the
  export gains a field, `export_bytes` must gain it too, or the full-budget round-trip test can export over the cap.
- **P18/P19 (frontend):** show "storage full" (PT507, with its hint to delete old classifications) and "file too
  large" (PT413) as distinct messages, and tell them apart from "not an export" (22023).
- **Open limitation, left to S3:** nothing in front of PostgREST limits a request body. The local Kong config has (as found in the P3b review)
  `client_max_body_size 0`, and the hosted gateway's limit is unknown. The 4 MB check runs only after the whole
  body has been received and parsed, so S3 should set a body limit of a few MB at the gateway.
- **Revisit** if the hosting target turns out larger than 1 GB, or if option D (a set-based import) is measured:
  either would allow a larger cap.
