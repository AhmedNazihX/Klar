-- import_my_data accepts every file export_my_data can produce (story P3b).
--
-- The 5 MB cap from the user-data migration rejected genuine exports: a classification result may
-- be up to 256 kB, so about 20 maximum-size (or 170 typical) classifications already exceeded it.
-- The largest export is set by Postgres itself: export_my_data returns one jsonb value, and a jsonb
-- value holds at most 268435455 bytes (255 MiB; a larger one fails with "total size of jsonb ...
-- exceeds the maximum"). import_my_data's argument is a jsonb value too, so it has the same bound,
-- and a separate byte cap could only ever reject an export. The cap is therefore dropped; the format
-- and version checks still reject a file that isn't an export.
--
-- `create or replace` keeps the function's owner, grants and revokes; only the body changes.
create or replace function public.import_my_data(data jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
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
