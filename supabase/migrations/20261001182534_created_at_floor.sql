-- A lower limit for created_at on the user-data tables (story P3b).
--
-- stamp_timestamps() capped created_at at now() but set no lower limit, so a client (or an import
-- file) could store -infinity or year 0001. Such a value breaks sorting, the export and date decoding
-- (psycopg cannot decode it). created_at may now be no earlier than created_at_floor, the day the
-- user-data schema went in (migration 20260928210100): no genuine row can be older. A fixed floor
-- rather than the owner's auth.users.created_at, because an import restores a file into a newer
-- session, and its dates must survive. An earlier value is rejected (22008), not clamped, so a bad
-- import fails as a whole instead of silently reordering its rows.
--
-- `create or replace` keeps the function's owner, revokes and the four triggers that call it.
create or replace function private.stamp_timestamps()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  -- The day the user-data schema went in; no row can genuinely be created before it.
  created_at_floor constant timestamptz := '2026-09-28 00:00:00+00';
begin
  if tg_op = 'INSERT' then
    new.created_at := least(coalesce(new.created_at, now()), now());
    if new.created_at < created_at_floor then
      raise exception 'created_at % is earlier than %', new.created_at, created_at_floor
        using errcode = '22008';
    end if;
  else
    new.created_at := old.created_at;
  end if;
  new.updated_at := now();
  return new;
end
$$;
