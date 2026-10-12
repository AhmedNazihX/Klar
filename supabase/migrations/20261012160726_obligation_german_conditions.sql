-- German conditions and SME relief for the duties (story P11): `applies_if` and `relief_note` were
-- English only, so German screens and reports showed "Nur wenn: You control the input data.".
-- Generated, like the other columns, from supabase/seed/obligations.yaml.
--
-- Additive and nullable, as in 20261007085135_obligation_texts.sql: every worktree shares the local
-- database, and a seed that doesn't know these columns yet must keep inserting rows. The rule "a
-- German twin wherever the English text is set" is enforced by the YAML loader
-- (aiact.obligations.list) and the seed tests.

alter table public.obligations
  add column applies_if_de text check (length(applies_if_de) > 0),
  add column relief_note_de text check (length(relief_note_de) > 0);

comment on column public.obligations.applies_if_de is 'The condition (applies_if) in German.';
comment on column public.obligations.relief_note_de is 'The SME relief (relief_note) in German.';
