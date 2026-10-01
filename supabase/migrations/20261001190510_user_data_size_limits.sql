-- User-data size limits (story P3b, decision 027): a 4 MB import cap, and a per-user storage budget
-- that keeps every account's export within it.
--
-- import_my_data reads the whole account as one jsonb document, and one call needs about 20 times the
-- document's size in backend memory (measured: 5 MB -> +102 MiB, 64 MB -> +1279 MiB, about a second
-- each, so the 8 s statement_timeout never stops it first). Four imports at once on a 1 GB instance
-- leave about 100 MiB each, so the cap is 4 MB. The budget makes sure no account can grow past what
-- one import takes: every genuine export stays importable.

-- 1. The import cap. The function is unchanged apart from the size check.
create or replace function public.import_my_data(data jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  -- One import needs about 20 times this in backend memory (decision 027). The storage budget in
  -- private.track_storage() keeps every export at or under it.
  max_bytes constant integer := 4 * 1024 * 1024;
  uid uuid := auth.uid();
  inventory jsonb;
  item jsonb;
  new_inventory_id uuid;
  new_system_id uuid;
  added_inventories bigint := 0;
  added_systems bigint := 0;
  added_classifications bigint := 0;
  added_answers bigint := 0;
  added bigint;
begin
  if uid is null then
    raise exception 'import_my_data needs a signed-in session' using errcode = '42501';
  end if;
  if data is null then
    raise exception 'import file is empty' using errcode = '22023';
  end if;
  -- PT413: PostgREST answers HTTP 413 (Payload Too Large), so the app can tell this from a bad file.
  if octet_length(data::text) > max_bytes then
    raise exception 'import file is larger than % bytes', max_bytes using errcode = 'PT413';
  end if;
  if data ->> 'format' is distinct from 'aiact-user-data' or data -> 'version' is distinct from '1'
     or jsonb_typeof(data -> 'inventories') is distinct from 'array' then
    raise exception 'not an aiact-user-data version 1 export' using errcode = '22023';
  end if;

  for inventory in select value from jsonb_array_elements(data -> 'inventories') loop
    insert into public.inventories (user_id, name, created_at)
    values (uid, inventory ->> 'name', (inventory ->> 'created_at')::timestamptz)
    returning id into new_inventory_id;
    added_inventories := added_inventories + 1;

    for item in select value from jsonb_array_elements(coalesce(inventory -> 'systems', '[]')) loop
      insert into public.systems (user_id, inventory_id, name, description, created_at)
      values (uid, new_inventory_id, item ->> 'name', item ->> 'description',
              (item ->> 'created_at')::timestamptz)
      returning id into new_system_id;
      added_systems := added_systems + 1;

      insert into public.classifications
        (user_id, system_id, risk_class, status, law_version, result, created_at)
      select uid, new_system_id, c.risk_class, c.status, c.law_version, c.result, c.created_at
      from jsonb_to_recordset(coalesce(item -> 'classifications', '[]')) as c(
        risk_class text, status text, law_version text, result jsonb, created_at timestamptz
      );
      get diagnostics added = row_count;
      added_classifications := added_classifications + added;

      insert into public.interview_answers (user_id, system_id, template, question_key, answer)
      select uid, new_system_id, a.template, a.question_key, a.answer
      from jsonb_to_recordset(coalesce(item -> 'interview_answers', '[]')) as a(
        template text, question_key text, answer text
      );
      get diagnostics added = row_count;
      added_answers := added_answers + added;
    end loop;
  end loop;

  return jsonb_build_object(
    'inventories', added_inventories,
    'systems', added_systems,
    'classifications', added_classifications,
    'interview_answers', added_answers
  );
end
$$;

-- 2. The storage budget.
--
-- A row's stored size is the bytes it adds to export_my_data()'s text: the same object the export
-- builds for it (its child arrays empty, since children count themselves), plus 2 bytes for the ", "
-- that separates it from its neighbour. created_at is counted at its widest rendering (32 characters,
-- microseconds and offset), so the size never depends on the time or the session's time zone, and the
-- sum is never below the export. Keep the objects in step with export_my_data().
create function private.export_bytes(table_name text, item jsonb)
returns bigint
language sql
immutable
set search_path = ''
as $$
  select 2 + octet_length((
    case table_name
      when 'inventories' then jsonb_build_object(
        'name', item -> 'name',
        'created_at', '2026-01-01T00:00:00.000000+00:00',
        'systems', '[]'::jsonb
      )
      when 'systems' then jsonb_build_object(
        'name', item -> 'name',
        'description', item -> 'description',
        'created_at', '2026-01-01T00:00:00.000000+00:00',
        'classifications', '[]'::jsonb,
        'interview_answers', '[]'::jsonb
      )
      when 'classifications' then jsonb_build_object(
        'risk_class', item -> 'risk_class',
        'status', item -> 'status',
        'law_version', item -> 'law_version',
        'result', item -> 'result',
        'created_at', '2026-01-01T00:00:00.000000+00:00'
      )
      when 'interview_answers' then jsonb_build_object(
        'template', item -> 'template',
        'question_key', item -> 'question_key',
        'answer', item -> 'answer'
      )
    end
  )::text)
$$;

revoke execute on function private.export_bytes(text, jsonb) from public, anon, authenticated;

-- Each user's running total. A running total rather than a sum over the user's rows on every write:
-- the sum would read (and detoast) up to 4 MB per insert, and an import of n rows would read it n times.
create table private.storage_usage (
  user_id uuid primary key references auth.users (id) on delete cascade,
  bytes bigint not null default 0
);

comment on table private.storage_usage is 'Bytes each user''s rows add to their export (decision 027).';

-- Not exposed through the Data API (schema private); RLS without policies as a second guard.
alter table private.storage_usage enable row level security;
revoke all on private.storage_usage from public, anon, authenticated;

-- After each write, moves the row's size into its owner's total and rejects a write that grows the
-- total past the budget (the whole statement, so a whole import, rolls back).
--
-- Concurrency: the upsert locks the user's storage_usage row until the transaction ends, so a second
-- writer for the same user waits, then re-reads the committed total and is checked against it. That
-- row lock does the job a per-user pg_advisory_xact_lock would, without a second lock to keep in step.
-- Deletes only subtract (an update, never an insert), so a cascade from a deleted auth user can't
-- re-create its total. Security definer, because the Data API roles have no access to private; it
-- touches only the total of the row's own user_id, which RLS has already checked.
create function private.track_storage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  -- The import cap (import_my_data's max_bytes) less 1 kB for the export's envelope (format, version,
  -- exported_at and the inventories array: about 100 bytes).
  budget constant bigint := 4 * 1024 * 1024 - 1024;
  old_bytes bigint := 0;
  new_bytes bigint := 0;
  total bigint;
begin
  if tg_op in ('UPDATE', 'DELETE') then
    old_bytes := private.export_bytes(tg_table_name, to_jsonb(old));
    update private.storage_usage set bytes = bytes - old_bytes where user_id = old.user_id;
  end if;
  if tg_op in ('INSERT', 'UPDATE') then
    new_bytes := private.export_bytes(tg_table_name, to_jsonb(new));
    insert into private.storage_usage as u (user_id, bytes) values (new.user_id, new_bytes)
    on conflict (user_id) do update set bytes = u.bytes + excluded.bytes
    returning u.bytes into total;
    -- A write that doesn't grow the data passes, so an account over the budget can still shrink.
    if total > budget and new_bytes > old_bytes then
      -- PT507: PostgREST answers HTTP 507 (Insufficient Storage).
      raise exception 'storage full: your saved data would exceed % bytes', budget
        using errcode = 'PT507',
              hint = 'Delete classifications, systems or inventories you no longer need.';
    end if;
  end if;
  return null;
end
$$;

revoke execute on function private.track_storage() from public, anon, authenticated;

create trigger inventories_track_storage after insert or update or delete on public.inventories
  for each row execute function private.track_storage();
create trigger systems_track_storage after insert or update or delete on public.systems
  for each row execute function private.track_storage();
create trigger classifications_track_storage after insert or update or delete
  on public.classifications
  for each row execute function private.track_storage();
create trigger interview_answers_track_storage after insert or update or delete
  on public.interview_answers
  for each row execute function private.track_storage();

-- The totals of the rows already stored.
insert into private.storage_usage (user_id, bytes)
select user_id, sum(bytes)
from (
  select t.user_id, private.export_bytes('inventories', to_jsonb(t)) as bytes
  from public.inventories t
  union all
  select t.user_id, private.export_bytes('systems', to_jsonb(t)) from public.systems t
  union all
  select t.user_id, private.export_bytes('classifications', to_jsonb(t)) from public.classifications t
  union all
  select t.user_id, private.export_bytes('interview_answers', to_jsonb(t))
  from public.interview_answers t
) as rows
group by user_id;
