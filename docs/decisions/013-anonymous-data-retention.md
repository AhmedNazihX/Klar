# 013 · Inactive anonymous data is deleted after 30 days

- **Date:** 2026-09-28
- **Story:** P3 (docs/BACKLOG.md)
- **Status:** accepted (the user confirmed 30 days on 2026-09-28)

## Question
INIT › Ethical considerations (Confidential company information) promises "automatic deletion of inactive
anonymous data", and INIT › Open questions leaves the retention period open. P3's pg_cron cleanup needs a
number: too short loses a returning user's inventory, too long keeps confidential descriptions longer than needed.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| 30 days | Nothing measured: a policy choice | Proposed by the P3 worker; the example period in Supabase's anonymous sign-in docs | P3 worker report; Supabase docs (anonymous sign-ins) |
| Another period | Nothing measured | Not chosen | — |

No run numbers are involved.

## Decision
Anonymous accounts inactive for 30 days are deleted with all their data. The user confirmed the value proposed in P3.

## Consequences
- **Where it lives:** the last statement of `supabase/migrations/20260928210100_user_data.sql` schedules the pg_cron
  job `purge-inactive-anonymous-users` daily at 03:17, calling
  `private.purge_inactive_anonymous_users(interval '30 days')`. `backend/tests/db/test_user_data_schema.py` holds the
  same value as `RETENTION`.
- **What counts as activity:** the latest of the auth account's creation or update, last sign-in, a session refresh,
  or the server-set `updated_at` of any of the user's rows. Clients can't write activity times: the
  `private.stamp_timestamps()` trigger sets `updated_at` to `now()` on every insert and update and caps `created_at`
  at `now()`, and the purge never reads `created_at`. So no row, direct or imported, can keep an account alive past
  the period. Accounts that are no longer anonymous are never deleted, and a retention under one day is refused.
- **Changing it:** a new migration that calls `cron.schedule('purge-inactive-anonymous-users', …)` with the new
  interval, plus the test constant. Don't edit the merged migration.
- **Privacy surface (P12):** the privacy notice should state the 30-day period.
- **Revisit** if users report losing inventories they came back for, or if the privacy review asks for a shorter period.
