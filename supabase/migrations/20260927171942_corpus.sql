-- Legal corpus: documents, provisions and their embeddings (story F4; INIT > Legal corpus).
--
-- The corpus is server-side data. The backend reads and writes it over a direct connection or with
-- the service role, so RLS is enabled with no policies and the Data API roles get no grants.

create extension if not exists vector with schema extensions;

-- One row per fetched text and language (the EN and DE versions of a law are two rows).
create table public.documents (
  id bigint generated always as identity primary key,
  title text not null,
  celex text,
  doc_type text not null check (doc_type in ('law', 'guideline', 'code')),
  status text not null check (status in ('final', 'draft', 'consolidated')),
  law_version text not null,
  language text not null check (language in ('en', 'de')),
  published_on date,
  in_force_from date,
  source_url text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (sha256),
  -- Target of the composite foreign key that keeps provisions.language equal to their document's.
  unique (id, language)
);

comment on table public.documents is 'Legal texts and Commission guidance in the corpus, one row per text and language.';
comment on column public.documents.law_version is 'Version label carried into every result that cites this document.';

-- One row per addressable unit: article paragraph, point, annex entry, recital or guideline example.
create table public.provisions (
  id bigint generated always as identity primary key,
  -- Stable, language-independent id that links EN and DE: art:6:3, annex:III:4:a, recital:53, guide:hr:ex:17.
  provision_id text not null check (provision_id ~ '^[a-z]+(:[A-Za-z0-9_.-]+)+$'),
  document_id bigint not null,
  language text not null check (language in ('en', 'de')),
  parent_id bigint references public.provisions (id) on delete cascade,
  heading text,
  text text not null,
  -- Half-open validity interval [valid_from, valid_to); null means unbounded.
  valid_from date,
  valid_to date,
  -- Set when the row comes from a Commission worked example, so held-out examples can be filtered out.
  source_example_id text,
  fts tsvector generated always as (
    to_tsvector(
      case language when 'de' then 'german'::regconfig else 'english'::regconfig end,
      coalesce(heading, '') || ' ' || text
    )
  ) stored,
  foreign key (document_id, language) references public.documents (id, language) on delete cascade,
  -- language follows from document_id; it leads here so this index also covers the foreign key.
  unique (document_id, language, provision_id),
  check (valid_to is null or valid_from is null or valid_to > valid_from)
);

comment on table public.provisions is 'Corpus units split along the legal structure, with keyword search.';
comment on column public.provisions.source_example_id is 'Commission worked-example id, null for law and guideline prose.';

create index provisions_provision_id_language_idx on public.provisions (provision_id, language);
create index provisions_parent_id_idx on public.provisions (parent_id);
create index provisions_fts_idx on public.provisions using gin (fts);

-- vector(1536) must match Settings.embedding_dimensions (default 1536). Changing it needs a new
-- migration and a full re-embed; pgvector's HNSW index caps vector at 2000 dimensions.
create table public.provision_embeddings (
  provision_row_id bigint not null references public.provisions (id) on delete cascade,
  model text not null,
  dims integer not null check (dims = 1536),
  embedding extensions.vector(1536) not null,
  created_at timestamptz not null default now(),
  primary key (provision_row_id, model)
);

comment on table public.provision_embeddings is 'Embeddings of provisions, one per provision and embedding model.';

create index provision_embeddings_embedding_idx
  on public.provision_embeddings using hnsw (embedding extensions.vector_cosine_ops);

alter table public.documents enable row level security;
alter table public.provisions enable row level security;
alter table public.provision_embeddings enable row level security;

revoke all on public.documents, public.provisions, public.provision_embeddings from anon, authenticated;
