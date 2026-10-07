-- P6 review fixes, round 2 (story P6): a run can be saved on a tool the user already has.
--
-- "Classify this tool" (a tool restored without its runs, or with a result Klar can't read) used to
-- save the finished run as a second tool: the first stayed "Not checked", the name was doubled and
-- the storage budget paid twice. save_classified_tool() takes an optional existing system id: with
-- one, the run is added to that tool as its next run; without one, it behaves as before. P5b's
-- follow-up re-runs reuse this path.
--
-- The new parameter goes last with a default, so a call without it (by name, as PostgREST makes
-- them) still resolves. A function's arguments can't be added in place: drop it and create it again.

drop function public.save_classified_tool(uuid, text, text, text, jsonb);

-- security invoker: every write runs as the caller, so the tables' owner-only RLS, their checks
-- (name and description lengths, the result's size and shape, the inputs' size) and their triggers
-- (timestamps, the run number, the storage budget's PT507) apply exactly as to a direct write.
--
-- Without target_system_id: the inventory (the target, else the caller's oldest, else a new one
-- named new_inventory_name), the system, then its first run. A target inventory that isn't the
-- caller's fails the (inventory_id, user_id) foreign key (23503).
--
-- With target_system_id: the run goes on that tool as run N+1 (the trigger numbers a system's runs),
-- and the tool takes the name and description it was run with, so its row and its result agree.
-- The inventory arguments aren't used. A system that isn't the caller's isn't updated (RLS) and
-- fails the run's (system_id, user_id) foreign key (23503), so nothing is written.
create function public.save_classified_tool(
  target_inventory_id uuid,
  new_inventory_name text,
  tool_name text,
  tool_description text,
  tool_result jsonb,
  target_system_id uuid default null
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  inventory_id uuid := target_inventory_id;
  tool_id uuid := target_system_id;
begin
  if uid is null then
    raise exception 'save_classified_tool needs a signed-in session' using errcode = '42501';
  end if;
  if jsonb_typeof(tool_result) is distinct from 'object' then
    raise exception 'the result must be a JSON object' using errcode = '22023';
  end if;

  if tool_id is not null then
    update public.systems s
    set name = tool_name, description = tool_description
    where s.id = tool_id
      and (s.name, s.description) is distinct from (tool_name, tool_description);
  else
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
  end if;

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

comment on function public.save_classified_tool(uuid, text, text, text, jsonb, uuid) is
  'Saves a classified run in one transaction, as the caller: on target_system_id as its next run '
  '(Classify this tool; P5b''s follow-up re-runs), else as a new tool (its inventory if needed, '
  'the system and its first run).';

-- Only with a session: functions are executable by PUBLIC by default.
revoke execute on function public.save_classified_tool(uuid, text, text, text, jsonb, uuid)
  from public, anon;
grant execute on function public.save_classified_tool(uuid, text, text, text, jsonb, uuid)
  to authenticated;
