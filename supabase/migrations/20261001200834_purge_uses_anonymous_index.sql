-- The inactivity cleanup's target select can use auth.users' is_anonymous index (story P3b,
-- decision 027).
--
-- private.is_inactive_anonymous_user sets search_path, so Postgres can't inline it: the target
-- select was a full scan of auth.users with one function call per row. A plain `u.is_anonymous`
-- in front lets the planner use users_is_anonymous_idx and call the function only for anonymous
-- users. The rule itself stays in the function. The delete's re-check already goes by primary key
-- (`u.id = any(targets)`).
--
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
  where u.is_anonymous and private.is_inactive_anonymous_user(u, retention, as_of);
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
