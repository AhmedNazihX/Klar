-- The inactivity cleanup can be scoped to given users (story F9).
--
-- All worktrees share one local database, and the tests ran the cleanup over every stale anonymous
-- user in it: it waited on any row another session held (another worktree's tests, a UI
-- reviewer's anonymous user), with nothing to end the wait. `only_users` limits the cleanup to
-- those ids, so a test touches only the users it made. Its default, null, keeps the cleanup as it
-- was: the cron job's `purge_inactive_anonymous_users(interval '30 days')` still covers everyone.
--
-- A new parameter changes the signature, which `create or replace` can't do: the function is
-- dropped and made again, and its revokes with it. The cron job calls it by name, so it needs no
-- change.
drop function private.purge_inactive_anonymous_users(interval, timestamptz);

create function private.purge_inactive_anonymous_users(
  retention interval,
  as_of timestamptz default now(),
  only_users uuid[] default null
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
  where u.is_anonymous
    and (only_users is null or u.id = any(only_users))
    and private.is_inactive_anonymous_user(u, retention, as_of);
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

comment on function private.purge_inactive_anonymous_users(interval, timestamptz, uuid[]) is
  'Deletes anonymous users inactive for longer than `retention` at `as_of`, with their data; '
  '`only_users` (null: everyone) limits it to those ids. Returns the number deleted.';

revoke execute on function private.purge_inactive_anonymous_users(interval, timestamptz, uuid[])
  from public, anon, authenticated;
