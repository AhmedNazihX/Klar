-- P19 review fixes (story P19; decision 027).
--
-- 1. The child tables' unique keys include user_id. With (system_id, ...) alone, user B inserting
--    under user A's system_id hit A's row first: 23505 when A had a matching run, answer or tick,
--    23503 when not, which told B what A had stored, and B's insert could wait on A's uncommitted
--    one. Keyed under the owner, another user's row never collides, and the (system_id, user_id)
--    foreign key always answers 23503. The keys lead with (system_id, user_id), so they also cover
--    that foreign key.
-- 2. duty_progress's tick time is its created_at, so private.stamp_timestamps() (the clamp and the
--    date floor) covers it like every other table; private.stamp_done_at(), a copy of it, is gone.
--    The export calls it created_at too. A row exists only while the duty is ticked, so its
--    creation time is when it was ticked.
-- 3. One storage budget: private.storage_budget(), read by private.track_storage() and
--    public.my_data_counts(). import_my_data keeps its own max_bytes (the cap), because it runs as
--    the caller, who has no access to schema private.

-- 1. Unique keys under the owner.
alter table public.classifications
  drop constraint classifications_system_run_no_key,
  add constraint classifications_system_user_run_no_key unique (system_id, user_id, run_no);
alter table public.duty_progress
  drop constraint duty_progress_system_id_obligation_key_key,
  add constraint duty_progress_system_user_obligation_key_key
    unique (system_id, user_id, obligation_key);
alter table public.interview_answers
  drop constraint interview_answers_system_id_template_question_key_key,
  add constraint interview_answers_system_user_template_question_key_key
    unique (system_id, user_id, template, question_key);

-- The next run number among the owner's runs of the system (the new key's order). `create or
-- replace` keeps the revokes and the trigger.
create or replace function private.number_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  select coalesce(max(c.run_no), 0) + 1 into new.run_no
  from public.classifications c
  where c.system_id = new.system_id and c.user_id = new.user_id;
  return new;
end
$$;

-- 2. The tick time is created_at, stamped like every other table's.
drop trigger duty_progress_stamp_done_at on public.duty_progress;
drop function private.stamp_done_at();
alter table public.duty_progress rename column done_at to created_at;
comment on column public.duty_progress.created_at is
  'When the duty was ticked (the row exists only while it is), set by private.stamp_timestamps().';
create trigger duty_progress_stamp_timestamps before insert or update on public.duty_progress
  for each row execute function private.stamp_timestamps();

-- The measure follows the export's new key. `create or replace` keeps the revokes; keep the objects
-- in step with export_my_data() below (decision 027).
create or replace function private.export_bytes(table_name text, item jsonb)
returns bigint
language sql
immutable
set search_path = ''
as $$
  select 2 + octet_length((
    case table_name
      when 'inventories' then jsonb_build_object(
        'name', item -> 'name',
        'company_name', item -> 'company_name',
        'staff_band', item -> 'staff_band',
        'turnover_band', item -> 'turnover_band',
        'established_in', item -> 'established_in',
        'used_in', item -> 'used_in',
        'created_at', '2026-01-01T00:00:00.000000+00:00',
        'systems', '[]'::jsonb
      )
      when 'systems' then jsonb_build_object(
        'name', item -> 'name',
        'description', item -> 'description',
        'created_at', '2026-01-01T00:00:00.000000+00:00',
        'classifications', '[]'::jsonb,
        'interview_answers', '[]'::jsonb,
        'duty_progress', '[]'::jsonb
      )
      when 'classifications' then jsonb_build_object(
        'run_no', item -> 'run_no',
        'risk_class', item -> 'risk_class',
        'status', item -> 'status',
        'law_version', item -> 'law_version',
        'result', item -> 'result',
        'inputs', item -> 'inputs',
        'created_at', '2026-01-01T00:00:00.000000+00:00'
      )
      when 'interview_answers' then jsonb_build_object(
        'template', item -> 'template',
        'question_key', item -> 'question_key',
        'answer', item -> 'answer'
      )
      when 'duty_progress' then jsonb_build_object(
        'obligation_key', item -> 'obligation_key',
        'created_at', '2026-01-01T00:00:00.000000+00:00'
      )
    end
  )::text)
$$;

-- A tick's size changed with its key, so the totals are recomputed from the rows.
update private.storage_usage set bytes = 0;
insert into private.storage_usage as u (user_id, bytes)
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
  union all
  select t.user_id, private.export_bytes('duty_progress', to_jsonb(t)) from public.duty_progress t
) as rows
group by user_id
on conflict (user_id) do update set bytes = excluded.bytes;

-- Unchanged apart from the tick's created_at. `create or replace` keeps the grants and revokes.
create or replace function public.export_my_data()
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  select jsonb_build_object(
    'format', 'aiact-user-data',
    'version', 1,
    'exported_at', now(),
    'inventories', coalesce((
      select jsonb_agg(jsonb_build_object(
        'name', i.name,
        'company_name', i.company_name,
        'staff_band', i.staff_band,
        'turnover_band', i.turnover_band,
        'established_in', i.established_in,
        'used_in', i.used_in,
        'created_at', i.created_at,
        'systems', coalesce((
          select jsonb_agg(jsonb_build_object(
            'name', s.name,
            'description', s.description,
            'created_at', s.created_at,
            'classifications', coalesce((
              select jsonb_agg(jsonb_build_object(
                'run_no', c.run_no,
                'risk_class', c.risk_class,
                'status', c.status,
                'law_version', c.law_version,
                'result', c.result,
                'inputs', c.inputs,
                'created_at', c.created_at
              ) order by c.run_no)
              from public.classifications c where c.system_id = s.id and c.user_id = s.user_id
            ), '[]'::jsonb),
            'interview_answers', coalesce((
              select jsonb_agg(jsonb_build_object(
                'template', a.template,
                'question_key', a.question_key,
                'answer', a.answer
              ) order by a.template, a.question_key)
              from public.interview_answers a where a.system_id = s.id and a.user_id = s.user_id
            ), '[]'::jsonb),
            'duty_progress', coalesce((
              select jsonb_agg(jsonb_build_object(
                'obligation_key', d.obligation_key,
                'created_at', d.created_at
              ) order by d.obligation_key)
              from public.duty_progress d where d.system_id = s.id and d.user_id = s.user_id
            ), '[]'::jsonb)
          ) order by s.created_at, s.id)
          from public.systems s where s.inventory_id = i.id and s.user_id = i.user_id
        ), '[]'::jsonb)
      ) order by i.created_at, i.id)
      from public.inventories i
      where i.user_id = (select auth.uid())
    ), '[]'::jsonb)
  )
$$;

-- Unchanged apart from the tick's created_at. A file's run_no isn't read: the runs are added in the
-- file's order (the export's is run_no's) and numbered afresh, so they come out 1..n.
create or replace function public.import_my_data(data jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  -- One import needs about 20 times this in backend memory (decision 027). The storage budget,
  -- private.storage_budget(), is this less 1 kB and keeps every export at or under it.
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
  added_duties bigint := 0;
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
    insert into public.inventories (user_id, name, company_name, staff_band, turnover_band,
                                    established_in, used_in, created_at)
    values (uid, inventory ->> 'name', inventory ->> 'company_name', inventory ->> 'staff_band',
            inventory ->> 'turnover_band', inventory ->> 'established_in', inventory ->> 'used_in',
            (inventory ->> 'created_at')::timestamptz)
    returning id into new_inventory_id;
    added_inventories := added_inventories + 1;

    for item in select value from jsonb_array_elements(coalesce(inventory -> 'systems', '[]')) loop
      insert into public.systems (user_id, inventory_id, name, description, created_at)
      values (uid, new_inventory_id, item ->> 'name', item ->> 'description',
              (item ->> 'created_at')::timestamptz)
      returning id into new_system_id;
      added_systems := added_systems + 1;

      insert into public.classifications
        (user_id, system_id, risk_class, status, law_version, result, inputs, created_at)
      select uid, new_system_id, c.risk_class, c.status, c.law_version, c.result, c.inputs,
             c.created_at
      from rows from (
        jsonb_to_recordset(coalesce(item -> 'classifications', '[]')) as (
          risk_class text, status text, law_version text, result jsonb, inputs jsonb,
          created_at timestamptz
        )
      ) with ordinality as c(risk_class, status, law_version, result, inputs, created_at, position)
      order by c.position;
      get diagnostics added = row_count;
      added_classifications := added_classifications + added;

      insert into public.interview_answers (user_id, system_id, template, question_key, answer)
      select uid, new_system_id, a.template, a.question_key, a.answer
      from jsonb_to_recordset(coalesce(item -> 'interview_answers', '[]')) as a(
        template text, question_key text, answer text
      );
      get diagnostics added = row_count;
      added_answers := added_answers + added;

      insert into public.duty_progress (user_id, system_id, obligation_key, created_at)
      select uid, new_system_id, d.obligation_key, d.created_at
      from jsonb_to_recordset(coalesce(item -> 'duty_progress', '[]')) as d(
        obligation_key text, created_at timestamptz
      );
      get diagnostics added = row_count;
      added_duties := added_duties + added;
    end loop;
  end loop;

  return jsonb_build_object(
    'inventories', added_inventories,
    'systems', added_systems,
    'classifications', added_classifications,
    'interview_answers', added_answers,
    'duty_progress', added_duties
  );
end
$$;

-- 3. The storage budget, in one place.
create function private.storage_budget()
returns bigint
language sql
immutable
set search_path = ''
as $$
  -- import_my_data's max_bytes (the 4 MB cap) less 1 kB for the export's envelope (format,
  -- version, exported_at and the inventories array: about 100 bytes).
  select 4 * 1024 * 1024 - 1024::bigint
$$;

comment on function private.storage_budget() is
  'Bytes a user''s rows may add to their export: import_my_data''s 4 MB cap less 1 kB (decision 027).';

revoke execute on function private.storage_budget() from public, anon, authenticated;

-- Unchanged apart from reading the budget from private.storage_budget(). `create or replace` keeps
-- the owner, revokes and triggers.
create or replace function private.track_storage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  budget constant bigint := private.storage_budget();
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

-- Unchanged apart from reading the budget from private.storage_budget(). company_profiles is the
-- YourData artboard's "Company profile" row.
create or replace function public.my_data_counts()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'my_data_counts needs a signed-in session' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'inventories', (select count(*) from public.inventories where user_id = uid),
    'company_profiles', (
      select count(*) from public.inventories
      where user_id = uid
        and num_nonnulls(company_name, staff_band, turnover_band, established_in, used_in) > 0
    ),
    'systems', (select count(*) from public.systems where user_id = uid),
    'classifications', (select count(*) from public.classifications where user_id = uid),
    'interview_answers', (select count(*) from public.interview_answers where user_id = uid),
    'duty_progress', (select count(*) from public.duty_progress where user_id = uid),
    'storage_bytes', coalesce(
      (select s.bytes from private.storage_usage s where s.user_id = uid), 0
    ),
    'storage_budget_bytes', private.storage_budget()
  );
end
$$;
