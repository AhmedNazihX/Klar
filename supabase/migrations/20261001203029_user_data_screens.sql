-- User data for the screens (story P19; decision 026 items 6, 7, 9 and 22; decision 027).
--
-- 1. A company profile on each inventory, with its size class (sme, smc, none) derived from the bands.
-- 2. Each classification's run number per system and the inputs the run used.
-- 3. duty_progress: the duties a user has ticked off, per system.
-- 4. The storage budget (decision 027) measures the new fields and table.
-- 5. export_my_data, import_my_data and delete_my_data carry them; my_data_counts() for Your data.
-- 6. The inactivity cleanup reads duty_progress's activity too.
--
-- No Q&A table: questions about the Act live only in the browser session (decision 026 item 6).
-- The export format stays version 1: every new field is optional on import, so older files still load.

-- 1. The company profile (decision 026 items 7 and 22). Every field is optional: "Skip for now" leaves
-- them null. Not an input to classification.
alter table public.inventories
  add column company_name text check (length(company_name) between 1 and 200),
  add column staff_band text check (staff_band in ('1-9', '10-49', '50-249', '250-749', '750+')),
  add column turnover_band text
    check (turnover_band in ('up_to_10m', 'up_to_50m', 'up_to_150m', 'over_150m')),
  -- ISO 3166-1 alpha-2 code of the country the company is established in (Art. 2(1)(c), Art. 22).
  add column established_in text check (established_in ~ '^[A-Z]{2}$'),
  -- Where the company's AI tools are used (Art. 2): only in the EU, or also outside it.
  add column used_in text check (used_in in ('eu', 'eu_and_outside')),
  -- SME: under 250 staff and turnover up to EUR 50 m (Recommendation 2003/361/EC). Small mid-cap:
  -- otherwise under 750 staff and turnover up to EUR 150 m (Omnibus). With turnover bands only, the
  -- alternative balance-sheet tests can't be applied. Null until both bands are set.
  add column size_class text generated always as (
    case
      when staff_band is null or turnover_band is null then null
      when staff_band in ('1-9', '10-49', '50-249') and turnover_band in ('up_to_10m', 'up_to_50m')
        then 'sme'
      when staff_band <> '750+' and turnover_band <> 'over_150m' then 'smc'
      else 'none'
    end
  ) stored;

comment on column public.inventories.size_class is
  'sme, smc (small mid-cap) or none, derived from staff_band and turnover_band; null without both.';

-- 2. Run numbers and inputs. run_no counts a system's runs from 1 and is set by the server (below);
-- inputs is the description and answers the run used (null on rows written before this migration).
alter table public.classifications
  add column run_no integer,
  add column inputs jsonb check (
    inputs is null or (
      jsonb_typeof(inputs) = 'object'
      and jsonb_typeof(inputs -> 'description') is not distinct from 'string'
      -- A description is at most 20000 characters; 128 kB leaves room for the answers.
      and octet_length(inputs::text) <= 131072
    )
  );

-- Number the existing runs in the order they were made, without touching their updated_at (the
-- cleanup's activity) or storage totals (recomputed in section 4).
alter table public.classifications disable trigger classifications_stamp_timestamps;
alter table public.classifications disable trigger classifications_track_storage;
update public.classifications c
set run_no = n.run_no
from (
  select id, row_number() over (partition by system_id order by created_at, id) as run_no
  from public.classifications
) as n
where c.id = n.id;
alter table public.classifications enable trigger classifications_stamp_timestamps;
alter table public.classifications enable trigger classifications_track_storage;

alter table public.classifications
  alter column run_no set not null,
  add constraint classifications_run_no_positive check (run_no > 0),
  add constraint classifications_system_run_no_key unique (system_id, run_no);

-- The next number for the row's system, whatever the client sends. Two sessions of one user can't
-- both read the same maximum: private.lock_storage() serialises a user's writes before any row, and
-- each query here takes a fresh snapshot. The unique constraint is the backstop. A deleted last run's
-- number is given again, so the numbers stay 1..n without gaps when only the latest run is undone.
create function private.number_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  select coalesce(max(c.run_no), 0) + 1 into new.run_no
  from public.classifications c
  where c.system_id = new.system_id;
  return new;
end
$$;

revoke execute on function private.number_run() from public, anon, authenticated;

create trigger classifications_number_run before insert on public.classifications
  for each row execute function private.number_run();

-- 3. Duty progress (decision 026 item 9): a row means the user ticked that duty for that system;
-- unticking deletes it. Kept under its system and owner like the other child tables.
create table public.duty_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  system_id uuid not null,
  -- An obligations.obligation_key (no foreign key: the obligations table is reseeded).
  obligation_key text not null
    check (length(obligation_key) <= 200 and obligation_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  -- When it was ticked: set like created_at on the other tables (private.stamp_done_at()).
  done_at timestamptz not null default now(),
  -- The cleanup's activity for this table.
  updated_at timestamptz not null default now(),
  foreign key (system_id, user_id) references public.systems (id, user_id) on delete cascade,
  unique (system_id, obligation_key)
);

comment on table public.duty_progress is 'Duties a visitor ticked off per system (obligations.obligation_key).';

create index duty_progress_user_system_idx on public.duty_progress (user_id, system_id);

-- private.stamp_timestamps()'s rule for done_at: never later than now() and never before the floor
-- (the same date as there), kept on update; updated_at is always now().
create function private.stamp_done_at()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  -- Keep in step with created_at_floor in private.stamp_timestamps().
  done_at_floor constant timestamptz := '2026-09-28 00:00:00+00';
begin
  if tg_op = 'INSERT' then
    new.done_at := least(coalesce(new.done_at, now()), now());
    if new.done_at < done_at_floor then
      raise exception 'done_at % is earlier than %', new.done_at, done_at_floor
        using errcode = '22008';
    end if;
  else
    new.done_at := old.done_at;
  end if;
  new.updated_at := now();
  return new;
end
$$;

revoke execute on function private.stamp_done_at() from public, anon, authenticated;

create trigger duty_progress_stamp_done_at before insert or update on public.duty_progress
  for each row execute function private.stamp_done_at();
create trigger duty_progress_lock_storage before insert or update or delete on public.duty_progress
  for each statement execute function private.lock_storage();
create trigger duty_progress_track_storage after insert or update or delete on public.duty_progress
  for each row execute function private.track_storage();

alter table public.duty_progress enable row level security;

create policy "Owners read their duty progress" on public.duty_progress for select
  to authenticated using ((select auth.uid()) = user_id);
create policy "Owners add duty progress" on public.duty_progress for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "Owners delete their duty progress" on public.duty_progress for delete
  to authenticated using ((select auth.uid()) = user_id);

revoke all on public.duty_progress from anon, authenticated;
-- A tick is set or cleared, never edited.
grant select, insert, delete on public.duty_progress to authenticated;

-- 4. The storage budget measures the new fields and table. Keep the objects in step with
-- export_my_data() below (decision 027); `create or replace` keeps the revokes.
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
        'done_at', '2026-01-01T00:00:00.000000+00:00'
      )
    end
  )::text)
$$;

-- Every row's size changed with the measure, so the totals are recomputed from the rows.
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
) as rows
group by user_id
on conflict (user_id) do update set bytes = excluded.bytes;

-- 5. Export, import, delete and counts.

-- `create or replace` keeps the function's owner, grants and revokes.
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
                'done_at', d.done_at
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

-- Unchanged apart from the new fields and table. A file's run_no isn't read: the runs are added in the
-- file's order (the export's is run_no's) and numbered afresh, so they come out 1..n.
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

      insert into public.duty_progress (user_id, system_id, obligation_key, done_at)
      select uid, new_system_id, d.obligation_key, d.done_at
      from jsonb_to_recordset(coalesce(item -> 'duty_progress', '[]')) as d(
        obligation_key text, done_at timestamptz
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

-- Unchanged apart from duty_progress. The profile goes with its inventory.
create or replace function public.delete_my_data()
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  n_answers bigint;
  n_duties bigint;
  n_classifications bigint;
  n_systems bigint;
  n_inventories bigint;
begin
  if uid is null then
    raise exception 'delete_my_data needs a signed-in session' using errcode = '42501';
  end if;
  delete from public.interview_answers where user_id = uid;
  get diagnostics n_answers = row_count;
  delete from public.duty_progress where user_id = uid;
  get diagnostics n_duties = row_count;
  delete from public.classifications where user_id = uid;
  get diagnostics n_classifications = row_count;
  delete from public.systems where user_id = uid;
  get diagnostics n_systems = row_count;
  delete from public.inventories where user_id = uid;
  get diagnostics n_inventories = row_count;
  return jsonb_build_object(
    'inventories', n_inventories,
    'systems', n_systems,
    'classifications', n_classifications,
    'interview_answers', n_answers,
    'duty_progress', n_duties
  );
end
$$;

comment on function public.delete_my_data() is 'Deletes all of the caller''s inventories (with their profiles), systems, classifications, answers and duty progress.';

-- The counts for Your data, and the storage used against the budget (private.track_storage()'s
-- `budget`). Security definer only to read the caller's own private.storage_usage row; every count is
-- filtered on the caller's auth.uid(), so it never reads anyone else's rows.
create function public.my_data_counts()
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
    -- Keep in step with `budget` in private.track_storage().
    'storage_budget_bytes', 4 * 1024 * 1024 - 1024
  );
end
$$;

comment on function public.my_data_counts() is 'Row counts of the caller''s data per kind, and their stored bytes against the budget.';

revoke execute on function public.my_data_counts() from public, anon;
grant execute on function public.my_data_counts() to authenticated;

-- 6. The cleanup's activity rule gains duty_progress. `create or replace` keeps the revokes, and
-- private.purge_inactive_anonymous_users() calls it by name.
create or replace function private.is_inactive_anonymous_user(
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
      (select max(a.updated_at) from public.interview_answers a where a.user_id = u.id),
      (select max(d.updated_at) from public.duty_progress d where d.user_id = u.id)
    ) < as_of - retention
$$;
