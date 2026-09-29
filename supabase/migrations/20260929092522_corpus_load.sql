-- What the corpus loader needs on top of F4's corpus schema (story C3; decisions 009 and 012).
--
-- provisions.is_held_out: a Pile B worked example is stored but kept out of search by default
-- (decision 012). The flag comes from the parsed guideline rows, so retrieval (C6) can filter on it
-- without reading the benchmark split.
--
-- documents.load_sha256: sha256 of the provision rows the loader built for the document. The raw
-- file's sha256 alone misses a parser fix, and the consolidated text's slices also depend on the
-- original text and the Omnibus; a reload happens when either hash changes.

alter table public.provisions
  add column is_held_out boolean not null default false,
  add constraint provisions_held_out_is_example check (not is_held_out or source_example_id is not null);

comment on column public.provisions.is_held_out is
  'True for a held-out (Pile B) Commission example: stored, excluded from search by default (decision 012).';

alter table public.documents
  add column load_sha256 text check (load_sha256 ~ '^[0-9a-f]{64}$');

comment on column public.documents.load_sha256 is
  'sha256 of the provision rows `aiact corpus load` built; null until the loader writes the document.';
