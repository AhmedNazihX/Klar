-- P6 review fixes (story P6): a tool's name may be left out, and a classified tool is saved in one
-- transaction.
--
-- 1. systems.name is optional. The Classify form leaves the name optional, and the screens show a
--    placeholder ("Your tool" / "Ihr Tool") in the reader's language when there is none; storing
--    the placeholder fixed it in one language and made every unnamed tool a look-alike. The length
--    check stays for a name that is given. The readers take a null: export_my_data() writes
--    "name": null, import_my_data() reads a missing or null name as null, private.export_bytes()
--    measures the null the export writes, and inventory_tools passes it through.
-- 2. public.save_classified_tool(): the inventory if the caller has none, the system and its first
--    classification, all or nothing. The browser used to write them one by one and delete the system
--    when the run couldn't be written, a delete whose own failure left a tool without a result.

-- 1. An optional name.
alter table public.systems alter column name drop not null;

comment on column public.systems.name is
  'The name the user gave the tool, or null: the screens then show a placeholder in their language.';

-- 2. Save a classified tool.
--
-- security invoker: every insert runs as the caller, so the tables' owner-only RLS, their checks
-- (name and description lengths, the result's size and shape, the inputs' size) and their triggers
-- (timestamps, the run number, the storage budget's PT507) apply exactly as to a direct insert. A
-- target inventory that isn't the caller's fails the (inventory_id, user_id) foreign key (23503).
-- Without a target it takes the caller's oldest inventory, or creates one named new_inventory_name.
create function public.save_classified_tool(
  target_inventory_id uuid,
  new_inventory_name text,
  tool_name text,
  tool_description text,
  tool_result jsonb
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  inventory_id uuid := target_inventory_id;
  tool_id uuid;
begin
  if uid is null then
    raise exception 'save_classified_tool needs a signed-in session' using errcode = '42501';
  end if;
  if jsonb_typeof(tool_result) is distinct from 'object' then
    raise exception 'the result must be a JSON object' using errcode = '22023';
  end if;

  if inventory_id is null then
    select i.id into inventory_id
    from public.inventories i
    where i.user_id = uid
    order by i.created_at, i.id
    limit 1;
  end if;
  if inventory_id is null then
    insert into public.inventories (name) values (new_inventory_name)
    returning id into inventory_id;
  end if;

  insert into public.systems (inventory_id, name, description)
  values (inventory_id, tool_name, tool_description)
  returning id into tool_id;

  -- The headline columns come from the result; a missing one fails their not-null (23502) or
  -- check (23514) constraints, and the whole save with it.
  insert into public.classifications (system_id, risk_class, status, law_version, result, inputs)
  values (
    tool_id,
    tool_result ->> 'risk_class',
    tool_result ->> 'status',
    tool_result ->> 'law_version',
    tool_result,
    jsonb_build_object('description', tool_description, 'answers', '{}'::jsonb)
  );

  return tool_id;
end
$$;

comment on function public.save_classified_tool(uuid, text, text, text, jsonb) is
  'Adds a classified tool (its inventory if needed, the system and its first run) in one transaction, as the caller.';

-- Only with a session: functions are executable by PUBLIC by default.
revoke execute on function public.save_classified_tool(uuid, text, text, text, jsonb)
  from public, anon;
grant execute on function public.save_classified_tool(uuid, text, text, text, jsonb)
  to authenticated;
