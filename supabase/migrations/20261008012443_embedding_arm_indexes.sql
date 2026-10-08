-- X1a's comparison arms (decision 003): one partial HNSW index per (model, dims) arm, on the same
-- cast and predicate search uses, as the default arm's index in the corpus migration. Qwen3 at 1024
-- dimensions, and OpenAI text-embedding-3-large shortened to 1536 (HNSW caps at 2000 dimensions).
create index if not exists provision_embeddings_qwen3_1024_idx
  on public.provision_embeddings
  using hnsw ((embedding::extensions.vector(1024)) extensions.vector_cosine_ops)
  where model = 'qwen/qwen3-embedding-8b' and dims = 1024;

create index if not exists provision_embeddings_openai3l_1536_idx
  on public.provision_embeddings
  using hnsw ((embedding::extensions.vector(1536)) extensions.vector_cosine_ops)
  where model = 'openai/text-embedding-3-large' and dims = 1536;
