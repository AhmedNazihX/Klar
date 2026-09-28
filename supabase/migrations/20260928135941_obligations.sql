-- Obligations table: role x risk class -> duty, article, applies_from (story C7; INIT > Scope,
-- Roles). Loaded from supabase/seed/obligations.sql, which `aiact obligations seed` generates from
-- supabase/seed/obligations.yaml, the source of truth that `list_obligations` also reads.
--
-- Reference data served by the backend, like the corpus: RLS is enabled with no policies and the
-- Data API roles get no grants.

create table public.obligations (
  id bigint generated always as identity primary key,
  -- The YAML entry the row expands from; one entry covers several roles, classes and routes.
  obligation_key text not null check (obligation_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  -- Table order within a (role, risk_class) list, as in the YAML.
  position integer not null check (position >= 0),
  role text not null check (role in ('provider', 'deployer', 'importer', 'distributor')),
  risk_class text not null
    check (risk_class in ('prohibited', 'high_risk', 'limited_risk', 'minimal_risk')),
  -- The high-risk route the date belongs to; null when the date is the same on every route.
  high_risk_route text check (high_risk_route in ('annex_iii', 'annex_i')),
  duty text not null check (length(duty) > 0),
  -- A provision id of the AI Act, e.g. art:26:1. Every duty cites an article.
  article text not null check (article ~ '^art:[0-9]+[a-z]?(:[A-Za-z0-9]+)*$'),
  applies_from date not null,
  applies_if text,
  -- True when the row informs rather than states a formal duty of this role (e.g. a distributor of a
  -- prohibited system: Art. 5 doesn't name distributors).
  is_informational boolean not null default false,
  relief_note text,
  note text,
  law_version text not null check (law_version in ('original', 'amended')),
  check (high_risk_route is null or risk_class = 'high_risk'),
  unique nulls not distinct (law_version, obligation_key, role, risk_class, high_risk_route)
);

comment on table public.obligations is
  'Duties per role and risk class with article and start date; generated from supabase/seed/obligations.yaml.';
comment on column public.obligations.high_risk_route is
  'annex_iii or annex_i when the start date depends on the high-risk route (Art. 113(c)); null otherwise.';

-- The lookup list_obligations does: one role and class, in table order.
create index obligations_lookup_idx
  on public.obligations (law_version, role, risk_class, position);

alter table public.obligations enable row level security;

revoke all on public.obligations from anon, authenticated;
revoke all on sequence public.obligations_id_seq from anon, authenticated;
