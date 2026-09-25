---
paths:
  - "backend/aiact/corpus/**"
  - "backend/aiact/retrieval/**"
  - "data/**"
---

# Rules for the corpus and retrieval code

- Never read `eval/`. The one exception is story C2, which reads the `pile_b` ID list in `eval/split.json` to drop or tag guideline examples. A hook blocks everything else on Corpus-lane branches.
- `provision_id` format: `art:<n>[:<para>[:<point>]]`, `annex:<roman>[:<point>[:<letter>]]`, `recital:<n>`, `guide:<doc>:<section|ex:<n>>`. IDs are identical across EN and DE.
- Every stored row carries its document, language, law version, validity dates and status (final, draft or consolidated). Guideline example chunks carry `source_example_id`.
- Ingestion is re-runnable and idempotent: the same input (by sha256) gives no change.
- Retrieval functions never call an LLM. Every result carries the law version and the disclaimer.
- Raw downloads go to `data/raw/` (gitignored). Resolve the data folder from `AIACT_DATA_DIR`, so that worktrees share one copy.
