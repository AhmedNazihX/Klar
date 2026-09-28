-- Legal corpus: documents, provisions and their embeddings (story F4; INIT > Legal corpus).
-- Versioning rules: docs/decisions/009-corpus-versioning.md.
--
-- The corpus is server-side data. The backend reads and writes it over a direct connection or with
-- the service role, so RLS is enabled with no policies and the Data API roles get no grants.

create extension if not exists vector with schema extensions;
-- Equality on bigint/text inside the gist exclusion constraint on provisions.
create extension if not exists btree_gist with schema extensions;

-- sha256 of a provision's heading and text, for spotting stale embeddings. convert_to() is only
-- STABLE (it depends on the encoding), so it can't sit in a generated column directly; the database
-- encoding is fixed at UTF8, which makes this wrapper deterministic.
create function public.provision_content_sha256(heading text, body text)
returns text
language sql
immutable
parallel safe
set search_path = ''
as $$
  select encode(sha256(convert_to(coalesce(heading, '') || E'\n' || body, 'UTF8')), 'hex')
$$;

revoke execute on function public.provision_content_sha256(text, text) from public, anon, authenticated;
grant execute on function public.provision_content_sha256(text, text) to service_role;

-- One row per text, law version and language (the EN and DE versions of a law are two rows).
create table public.documents (
  id bigint generated always as identity primary key,
  -- Family slug shared across languages and versions; matches the ids in data/manifest.yaml.
  doc_key text not null check (doc_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title text not null,
  celex text,
  doc_type text not null check (doc_type in ('law', 'guideline', 'code')),
  -- True for an act that amends another (the Digital Omnibus); version lookups never pick it.
  is_amending boolean not null default false,
  status text not null check (status in ('final', 'draft', 'consolidated')),
  -- 'original' (Official Journal text) or 'amended' (consolidated text) for the AI Act itself;
  -- null for guidance and for amending acts.
  law_version text check (law_version in ('original', 'amended')),
  language text not null check (language in ('en', 'de')),
  published_on date,
  in_force_from date,
  source_url text not null,
  -- For change detection on re-fetch, not identity: the same text may be loaded again.
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  check (not is_amending or doc_type = 'law'),
  check (doc_type <> 'law' or is_amending or law_version is not null),
  -- The loader's upsert target.
  unique nulls not distinct (doc_key, law_version, language),
  -- Target of the composite foreign key that keeps provisions.language equal to their document's.
  unique (id, language)
);

comment on table public.documents is 'Legal texts and Commission guidance in the corpus, one row per text, law version and language.';
comment on column public.documents.law_version is 'original | amended for the AI Act; carried into every result that cites this document.';
comment on column public.documents.is_amending is 'Amending act (Digital Omnibus): stored for citation, never picked by version lookups.';

-- One row per addressable unit and time slice: article paragraph, point, annex entry, recital or
-- guideline example. A provision that changes on a later date has one row per validity range.
create table public.provisions (
  id bigint generated always as identity primary key,
  -- Stable, language-independent id that links EN and DE: art:6:3, annex:III:4:a, recital:53, guide:hr:ex:17.
  provision_id text not null check (provision_id ~ '^[a-z]+(:[A-Za-z0-9_.-]+)+$'),
  document_id bigint not null,
  language text not null check (language in ('en', 'de')),
  parent_id bigint,
  heading text,
  text text not null,
  -- Half-open validity range [valid_from, valid_to). The loader sets valid_from (the document's
  -- in_force_from, or its published_on for guidance); a null valid_to means open-ended.
  valid_from date not null,
  valid_to date,
  -- Set when the row comes from a Commission worked example, so held-out examples can be filtered out.
  source_example_id text,
  fts tsvector generated always as (
    to_tsvector(
      case language when 'de' then 'german'::regconfig else 'english'::regconfig end,
      coalesce(heading, '') || ' ' || text
    )
  ) stored,
  -- Compared with provision_embeddings.content_sha256 to find embeddings of an older text.
  content_sha256 text generated always as (public.provision_content_sha256(heading, text)) stored,
  check (valid_to is null or valid_to > valid_from),
  foreign key (document_id, language) references public.documents (id, language) on delete cascade,
  -- Keeps a parent in the same document and language (not checked while parent_id is null).
  -- No action, checked at the end of the statement: a reload deletes all of a document's
  -- provisions in one statement, while deleting a single parent still fails loudly.
  foreign key (parent_id, document_id, language)
    references public.provisions (id, document_id, language),
  -- The loader's upsert target; language follows from document_id and leads so this index also
  -- covers the documents foreign key.
  unique (document_id, language, provision_id, valid_from),
  -- Target of the parent foreign key.
  unique (id, document_id, language),
  -- Time slices of one provision never overlap.
  exclude using gist (
    document_id with =,
    language with =,
    provision_id with =,
    daterange(valid_from, valid_to) with &&
  )
);

comment on table public.provisions is 'Corpus units split along the legal structure, one row per time slice, with keyword search.';
comment on column public.provisions.source_example_id is
  'Commission worked-example id, null for law and guideline prose. Exclude filters must keep nulls: '
  'source_example_id is null or not (source_example_id = any(...)).';

create index provisions_provision_id_language_idx on public.provisions (provision_id, language);
create index provisions_parent_idx on public.provisions (parent_id, document_id, language);
create index provisions_fts_idx on public.provisions using gin (fts);

-- One row per provision, embedding model and size, so X1 can compare arms (Qwen3 at 1536 or 1024,
-- OpenAI 3-large) side by side. The column is untyped; dims records and checks the size.
create table public.provision_embeddings (
  provision_row_id bigint not null references public.provisions (id) on delete cascade,
  model text not null,
  dims integer not null check (dims > 0),
  embedding extensions.vector not null,
  -- The provision's content_sha256 when this was embedded (copied by C4); a mismatch means stale.
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  check (extensions.vector_dims(embedding) = dims),
  primary key (provision_row_id, model, dims)
);

comment on table public.provision_embeddings is 'Embeddings of provisions, one per provision, embedding model and size.';

-- HNSW needs a fixed size, so each (model, dims) arm gets its own partial index on a cast. This one
-- is the default arm (Settings.embedding_dimensions = 1536); C4/X1 add a partial index per new arm.
-- To hit an index, a query must use the same cast and predicate, e.g.
--   where model = 'qwen/qwen3-embedding-8b' and dims = 1536
--   order by embedding::extensions.vector(1536) <=> $1::extensions.vector(1536) limit k
-- Filters (language, document, source_example_id) apply after the index scan, so C6 queries should
-- `set local hnsw.iterative_scan = relaxed_order` (pgvector 0.8) or raise hnsw.ef_search.
create index provision_embeddings_qwen3_1536_idx
  on public.provision_embeddings
  using hnsw ((embedding::extensions.vector(1536)) extensions.vector_cosine_ops)
  where model = 'qwen/qwen3-embedding-8b' and dims = 1536;

alter table public.documents enable row level security;
alter table public.provisions enable row level security;
alter table public.provision_embeddings enable row level security;

revoke all on public.documents, public.provisions, public.provision_embeddings from anon, authenticated;
revoke all on sequence public.documents_id_seq, public.provisions_id_seq from anon, authenticated;
