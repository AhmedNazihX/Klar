# 009 · Corpus versioning and embedding arms

- **Date:** 2026-09-27
- **Story:** F4 (docs/BACKLOG.md)
- **Status:** accepted (rule approved by the user in the F4 review)

## Question
How does the corpus schema tell the original AI Act text, the amended text and the Digital Omnibus apart,
and how does it hold provisions that change on a later date? INIT › Legal corpus says the amended text
wins and every answer names the version it used. The same review also settled how embeddings of
different sizes live side by side for X1 (INIT › Tech stack, Embeddings).

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| One row per provision, version as a column on provisions | Fit with "each result carries its law version" | Rejected: the version belongs to the text as fetched, not to each unit | F4 review |
| One document per (doc_key, law_version, language); time-sliced provision rows | Upsert key for C3, lookup for C5 | Chosen | F4 review |
| Omnibus as a third law_version | Would let version lookups return the amending act | Rejected: it amends the AI Act, it is not a version of it | F4 review |
| Fixed `vector(1536)` column | Supports X1's 1024-dim and OpenAI 3-large arms | Rejected: one size only | F4 review |
| Untyped `vector` + `dims`, one partial HNSW index per (model, dims) arm | Same | Chosen | F4 review |

No numbers were measured; this is a schema rule.

## Decision
- **Documents.** `doc_key` is the family slug shared across languages and matches the ids in
  `data/manifest.yaml` (`ai-act`, `omnibus`, `ai-act-consolidated`, `guide-definition`,
  `guide-prohibited`, `guide-high-risk-general`, `guide-high-risk-annex-i`, `guide-high-risk-annex-iii`,
  `guide-art50`, `code-of-practice-transparency`). `unique nulls not distinct (doc_key, law_version, language)`
  is the upsert target. `sha256` is for change detection only, not identity.
- **Versions.** The original Official Journal text has `law_version = 'original'`; the consolidated text
  has `'amended'`. Guidance and codes have a null `law_version`. Each document holds one law version.
- **Omnibus.** Stored as `doc_type = 'law'` with `is_amending = true` and a null `law_version`.
  `get_provision` and search version lookups never pick an amending act; it is cited only when an answer
  says a provision was changed by it. A check requires every non-amending law to have a `law_version`.
- **Time slices.** Within a document, a provision may have several rows with half-open ranges
  `[valid_from, valid_to)`. `valid_from` is required (the loader sets the document's `in_force_from`, or
  `published_on` for guidance); `valid_to > valid_from`; the unique key is
  `(document_id, language, provision_id, valid_from)`. A btree_gist exclusion constraint rejects
  overlapping slices of one provision.
- **Embeddings.** `embedding` is an untyped `vector` with `dims` checked `> 0` and equal to
  `vector_dims(embedding)`; the key is `(provision_row_id, model, dims)`. The default arm
  (`qwen/qwen3-embedding-8b`, 1536) has a partial HNSW cosine index on `embedding::vector(1536)`.

## Consequences
- C3 upserts documents on `(doc_key, law_version, language)` and provisions on
  `(document_id, language, provision_id, valid_from)`; it must set `valid_from` on every row.
- C5/C6 look up the current text as `law_version = 'amended' and not is_amending`, and pick the slice
  whose range contains the date asked about.
- C4/X1 add one partial HNSW index per new (model, dims) arm, in a new migration. A query hits an index
  only when it uses the same cast and predicate, for example
  `where model = 'qwen/qwen3-embedding-8b' and dims = 1536 order by embedding::vector(1536) <=> $1::vector(1536)`.
- Filters on language, document or `source_example_id` are applied after the HNSW scan, so C6 queries
  should `set local hnsw.iterative_scan = relaxed_order` (pgvector 0.8, installed 0.8.2) or raise
  `hnsw.ef_search`, or they may return fewer than k rows.
- Exclude filters on `source_example_id` must keep nulls:
  `source_example_id is null or not (source_example_id = any(...))`.
- Guidance keeps one row per `doc_key` and language: if the high-risk guidelines are finalised, the
  reload replaces the draft row (status `final`, new `sha256`). Revisit this if both the draft and the
  final text must stay retrievable, or if a German consolidation appears later than the English one.
