-- Obligation texts for the screens (story C9; decision 026): a short plain label per duty in English
-- and German, the formal duty in German, the provider layout's group and the drafting template a
-- duty links to. Generated, like the other columns, from supabase/seed/obligations.yaml.
--
-- Additive and nullable on purpose: every worktree shares the local database, and code that
-- doesn't know these columns yet (its seed and tests) must keep inserting rows. The rules "every
-- row has both labels and the German duty" and "every high-risk provider duty has a group" are
-- enforced where the rows come from: the Obligation model and the YAML loader (aiact.obligations),
-- and the seed tests. A later migration may make the texts not null once every branch carries them.

alter table public.obligations
  add column label_en text check (length(label_en) > 0),
  add column label_de text check (length(label_de) > 0),
  add column duty_de text check (length(duty_de) > 0),
  -- The provider layout's group (Build it right, Prove it, After launch).
  add column duty_group text check (duty_group in ('build', 'prove', 'after_launch')),
  -- The drafting template (P8a, P8b) that answers the duty, if any.
  add column document text check (document ~ '^[a-z0-9]+(_[a-z0-9]+)*$');

comment on column public.obligations.label_en is
  'Short plain label, as an action ("Keep the logs it creates for at least six months").';
comment on column public.obligations.label_de is 'The short label in German.';
comment on column public.obligations.duty_de is
  'The formal duty in German, in the terms of the official German text.';
comment on column public.obligations.duty_group is
  'build, prove or after_launch: the provider layout''s group; null on duties no provider has.';
comment on column public.obligations.document is
  'The drafting template key (P8a, P8b) for the duty, if any.';
