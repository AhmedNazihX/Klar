-- The inactivity cleanup takes its locks in the same order as a user's write (story P3b, decision
-- 027).
--
-- A user's write locks their storage_usage row first (private.lock_storage()), then takes KEY SHARE
-- on their auth.users row in its foreign-key check. The cleanup deleted the auth.users row first and
-- reached storage_usage only through the cascade, so a write racing the cleanup of the same user
-- could deadlock (40P01); if the cleanup was the one aborted, that day's purge of every inactive
-- user rolled back. Now the cleanup locks the targeted users' storage_usage rows first (in user_id
-- order), then deletes. Holding those locks also keeps the targets from writing in between, and the
-- delete re-checks the inactivity rule with a fresh snapshot, so a user who wrote just before the
-- lock is kept.

-- The rule itself, unchanged from the user-data migration: anonymous, and the latest of sign-in,
-- session refresh and the server-set updated_at of their rows is older than `as_of - retention`.
create function private.is_inactive_anonymous_user(
  u auth.users,
  retention interval,
  as_of timestamptz
)
returns boolean
language sql
stable
set search_path = ''
as $$
  select u.is_anonymous
    and greatest(
      u.created_at,
      u.updated_at,
      u.last_sign_in_at,
      (select max(greatest(s.updated_at, s.refreshed_at)) from auth.sessions s where s.user_id = u.id),
      (select max(i.updated_at) from public.inventories i where i.user_id = u.id),
      (select max(s.updated_at) from public.systems s where s.user_id = u.id),
      (select max(c.updated_at) from public.classifications c where c.user_id = u.id),
      (select max(a.updated_at) from public.interview_answers a where a.user_id = u.id)
    ) < as_of - retention
$$;

revoke execute on function private.is_inactive_anonymous_user(auth.users, interval, timestamptz)
  from public, anon, authenticated;

-- `create or replace` keeps the function's owner and revokes, and the cron job that calls it.
create or replace function private.purge_inactive_anonymous_users(
  retention interval,
  as_of timestamptz default now()
)
returns bigint
language plpgsql
set search_path = ''
as $$
declare
  targets uuid[];
  deleted bigint;
begin
  if retention is null or retention < interval '1 day' then
    raise exception 'retention must be at least one day, got %', retention using errcode = '22023';
  end if;
  if as_of is null then
    raise exception 'as_of must be a time' using errcode = '22023';
  end if;
  select coalesce(array_agg(u.id), '{}') into targets
  from auth.users u
  where private.is_inactive_anonymous_user(u, retention, as_of);
  perform from private.storage_usage s
  where s.user_id = any(targets)
  order by s.user_id
  for update;
  delete from auth.users u
  where u.id = any(targets) and private.is_inactive_anonymous_user(u, retention, as_of);
  get diagnostics deleted = row_count;
  return deleted;
end
$$;
