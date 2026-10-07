-- The inventory's tools, each with its latest run (story P6; artboard `Inventory`).
--
-- One row per system the caller owns, with the newest classification's run number, result and
-- time, or nulls while the tool has no run yet. The Inventory screen reads its table and company
-- summary from it, and a tool's result page reads one row by id.
--
-- security_invoker: the view reads systems and classifications as the caller, so their owner-only
-- RLS applies and nobody sees another user's tools (a plain view would run as its owner, postgres,
-- and bypass RLS). The lateral join matches on user_id as well, so it walks the
-- (system_id, user_id, run_no) unique key from its top.
--
-- The rows are what the browser wrote (P3): a result here is not a verified record, and the
-- screens never present it as one.
create view public.inventory_tools
with (security_invoker = true)
as
select
  s.id,
  s.inventory_id,
  s.name,
  s.description,
  s.created_at,
  latest.run_no,
  latest.result,
  latest.created_at as checked_at
from public.systems as s
left join lateral (
  select c.run_no, c.result, c.created_at
  from public.classifications as c
  where c.system_id = s.id and c.user_id = s.user_id
  order by c.run_no desc
  limit 1
) as latest on true;

comment on view public.inventory_tools is
  'The caller''s AI systems with their latest classification (security invoker: owner-only RLS applies).';

-- Read-only, and only with a session: Supabase's default privileges grant new public objects to
-- anon and authenticated, so take everything back first.
revoke all on public.inventory_tools from public, anon, authenticated;
grant select on public.inventory_tools to authenticated;
