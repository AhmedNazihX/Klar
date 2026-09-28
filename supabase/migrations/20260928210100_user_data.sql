-- User data: inventories, systems, classifications and interview answers (story P3; INIT > Scope
-- (Storage), Ethical considerations (Confidential information)).
--
-- Unlike the corpus, these tables are read and written by the browser through the Data API, as the
-- visitor's anonymous Supabase session (the `authenticated` role, `is_anonymous` in the JWT). Every
-- row carries the owner's auth.uid(); RLS limits each role to its own rows, and child rows reference
-- their parent together with user_id, so a row can never hang under another user's parent.
--
-- Also here: delete_my_data(), export_my_data() / import_my_data(jsonb), and a daily pg_cron job
-- that deletes anonymous users (and, by cascade, their data) after a period of inactivity.

create extension if not exists pg_cron with schema pg_catalog;

-- Functions the Data API must not expose: the updated_at trigger and the cleanup.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end
$$;

revoke execute on function private.set_updated_at() from public, anon, authenticated;

-- A named collection of a company's AI systems (the Inventory view, P6).
create table public.inventories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name text not null check (length(name) between 1 and 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Target of the children's (inventory_id, user_id) foreign key.
  unique (id, user_id)
);

comment on table public.inventories is 'A visitor''s AI inventory; owned by auth.uid(), private to them (RLS).';

-- One AI system as the visitor described it.
create table public.systems (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  inventory_id uuid not null,
  name text not null check (length(name) between 1 and 200),
  description text not null check (length(description) between 1 and 20000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (inventory_id, user_id) references public.inventories (id, user_id) on delete cascade,
  unique (id, user_id)
);

comment on table public.systems is 'An AI system in an inventory, with the description it was classified from.';

-- One engine run for a system. The full ClassificationResult is kept as JSON; the headline fields
-- are copied into columns for the overview table.
create table public.classifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  system_id uuid not null,
  risk_class text not null check (
    risk_class in ('out_of_scope', 'prohibited', 'high_risk', 'limited_risk', 'minimal_risk')
  ),
  status text not null check (status in ('decided', 'needs_more_information', 'legally_ambiguous')),
  law_version text not null check (law_version in ('original', 'amended')),
  result jsonb not null check (jsonb_typeof(result) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (system_id, user_id) references public.systems (id, user_id) on delete cascade
);

comment on table public.classifications is 'Classification results for a system (aiact.schemas.ClassificationResult as JSON).';

-- The visitor's answers in the guided documentation interview (P9), one per question and template.
create table public.interview_answers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  system_id uuid not null,
  -- The skeleton template, e.g. annex_iv, art_17, art_9, art_27.
  template text not null check (template ~ '^[a-z0-9]+(_[a-z0-9]+)*$'),
  question_key text not null check (length(question_key) between 1 and 200),
  answer text not null check (length(answer) <= 20000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (system_id, user_id) references public.systems (id, user_id) on delete cascade,
  unique (system_id, template, question_key)
);

comment on table public.interview_answers is 'Interview answers per system, template and question.';

-- user_id leads each index: RLS filters on it, and it also covers the composite foreign keys.
create index inventories_user_idx on public.inventories (user_id);
create index systems_user_inventory_idx on public.systems (user_id, inventory_id);
create index classifications_user_system_idx on public.classifications (user_id, system_id, created_at);
create index interview_answers_user_system_idx on public.interview_answers (user_id, system_id);

create trigger inventories_set_updated_at before update on public.inventories
  for each row execute function private.set_updated_at();
create trigger systems_set_updated_at before update on public.systems
  for each row execute function private.set_updated_at();
create trigger interview_answers_set_updated_at before update on public.interview_answers
  for each row execute function private.set_updated_at();

-- RLS: each signed-in visitor (anonymous or not) sees and changes only their own rows; the anon role
-- (no session) gets nothing. `(select auth.uid())` is evaluated once per statement, not per row.
alter table public.inventories enable row level security;
alter table public.systems enable row level security;
alter table public.classifications enable row level security;
alter table public.interview_answers enable row level security;

create policy "Owners read their inventories" on public.inventories for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "Owners add inventories" on public.inventories for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "Owners change their inventories" on public.inventories for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Owners delete their inventories" on public.inventories for delete to authenticated
  using ((select auth.uid()) = user_id);

create policy "Owners read their systems" on public.systems for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "Owners add systems" on public.systems for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "Owners change their systems" on public.systems for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Owners delete their systems" on public.systems for delete to authenticated
  using ((select auth.uid()) = user_id);

create policy "Owners read their classifications" on public.classifications for select
  to authenticated using ((select auth.uid()) = user_id);
create policy "Owners add classifications" on public.classifications for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "Owners delete their classifications" on public.classifications for delete
  to authenticated using ((select auth.uid()) = user_id);

create policy "Owners read their answers" on public.interview_answers for select to authenticated
  using ((select auth.uid()) = user_id);
create policy "Owners add answers" on public.interview_answers for insert to authenticated
  with check ((select auth.uid()) = user_id);
create policy "Owners change their answers" on public.interview_answers for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Owners delete their answers" on public.interview_answers for delete to authenticated
  using ((select auth.uid()) = user_id);

revoke all on public.inventories, public.systems, public.classifications, public.interview_answers
  from anon, authenticated;
grant select, insert, update, delete on public.inventories, public.systems, public.interview_answers
  to authenticated;
-- A classification is a record of a run: it can be deleted, not rewritten.
grant select, insert, delete on public.classifications to authenticated;

-- delete my data: removes every row the caller owns and returns the counts per table. Runs as the
-- caller, so RLS still applies. The anonymous auth user itself is left to the inactivity cleanup.
create function public.delete_my_data()
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  n_answers bigint;
  n_classifications bigint;
  n_systems bigint;
  n_inventories bigint;
begin
  if uid is null then
    raise exception 'delete_my_data needs a signed-in session' using errcode = '42501';
  end if;
  delete from public.interview_answers where user_id = uid;
  get diagnostics n_answers = row_count;
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
    'interview_answers', n_answers
  );
end
$$;

comment on function public.delete_my_data() is 'Deletes all of the caller''s inventories, systems, classifications and answers.';

-- Export: the caller's data as one nested JSON document, without ids or user ids, so it can be
-- imported into any other session. `format` and `version` identify the file on import.
create function public.export_my_data()
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
        'created_at', i.created_at,
        'systems', coalesce((
          select jsonb_agg(jsonb_build_object(
            'name', s.name,
            'description', s.description,
            'created_at', s.created_at,
            'classifications', coalesce((
              select jsonb_agg(jsonb_build_object(
                'risk_class', c.risk_class,
                'status', c.status,
                'law_version', c.law_version,
                'result', c.result,
                'created_at', c.created_at
              ) order by c.created_at, c.id)
              from public.classifications c where c.system_id = s.id and c.user_id = s.user_id
            ), '[]'::jsonb),
            'interview_answers', coalesce((
              select jsonb_agg(jsonb_build_object(
                'template', a.template,
                'question_key', a.question_key,
                'answer', a.answer
              ) order by a.template, a.question_key)
              from public.interview_answers a where a.system_id = s.id and a.user_id = s.user_id
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

comment on function public.export_my_data() is 'The caller''s data as a nested JSON document (format aiact-user-data, version 1).';

-- Import: adds the inventories of an export_my_data() document to the caller's data, with new ids.
-- Existing rows are kept. The table checks validate every field; any error rolls the import back.
-- Returns the number of rows added per table.
create function public.import_my_data(data jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  -- Far above a real inventory, well below what would strain the database.
  max_bytes constant integer := 5 * 1024 * 1024;
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
  if data is null or octet_length(data::text) > max_bytes then
    raise exception 'import file is empty or larger than % bytes', max_bytes using errcode = '22023';
  end if;
  if data ->> 'format' is distinct from 'aiact-user-data' or data -> 'version' is distinct from '1'
     or jsonb_typeof(data -> 'inventories') is distinct from 'array' then
    raise exception 'not an aiact-user-data version 1 export' using errcode = '22023';
  end if;

  for inventory in select value from jsonb_array_elements(data -> 'inventories') loop
    insert into public.inventories (user_id, name)
    values (uid, inventory ->> 'name')
    returning id into new_inventory_id;
    added_inventories := added_inventories + 1;

    for item in select value from jsonb_array_elements(coalesce(inventory -> 'systems', '[]')) loop
      insert into public.systems (user_id, inventory_id, name, description)
      values (uid, new_inventory_id, item ->> 'name', item ->> 'description')
      returning id into new_system_id;
      added_systems := added_systems + 1;

      insert into public.classifications
        (user_id, system_id, risk_class, status, law_version, result, created_at)
      select uid, new_system_id, c.risk_class, c.status, c.law_version, c.result,
             coalesce(c.created_at, now())
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

comment on function public.import_my_data(jsonb) is 'Adds the inventories of an export_my_data() document to the caller''s data.';

revoke execute on function public.delete_my_data(), public.export_my_data(),
  public.import_my_data(jsonb) from public, anon;
grant execute on function public.delete_my_data(), public.export_my_data(),
  public.import_my_data(jsonb) to authenticated;

-- Inactivity cleanup: deletes anonymous users whose last activity is older than `retention`; their
-- data goes with them (on delete cascade). Activity is the latest of sign-in, session refresh (the
-- client refreshes its token while the app is open) and any change to their data. Accounts that are
-- no longer anonymous are never touched. Returns the number of users deleted.
create function private.purge_inactive_anonymous_users(retention interval)
returns bigint
language plpgsql
set search_path = ''
as $$
declare
  deleted bigint;
begin
  if retention is null or retention < interval '1 day' then
    raise exception 'retention must be at least one day, got %', retention using errcode = '22023';
  end if;
  delete from auth.users u
  where u.is_anonymous
    and greatest(
      u.created_at,
      u.updated_at,
      u.last_sign_in_at,
      (select max(greatest(s.updated_at, s.refreshed_at)) from auth.sessions s where s.user_id = u.id),
      (select max(i.updated_at) from public.inventories i where i.user_id = u.id),
      (select max(s.updated_at) from public.systems s where s.user_id = u.id),
      (select max(c.created_at) from public.classifications c where c.user_id = u.id),
      (select max(a.updated_at) from public.interview_answers a where a.user_id = u.id)
    ) < now() - retention;
  get diagnostics deleted = row_count;
  return deleted;
end
$$;

revoke execute on function private.purge_inactive_anonymous_users(interval)
  from public, anon, authenticated;

-- Daily at 03:17 UTC. The retention period is the argument; to change it, run cron.schedule again
-- with the same job name (it replaces the job) in a new migration.
select cron.schedule(
  'purge-inactive-anonymous-users',
  '17 3 * * *',
  $$select private.purge_inactive_anonymous_users(interval '30 days')$$
);
