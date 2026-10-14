---
paths:
  - "eval/**"
---

# Rules for eval/ (benchmark cases, split, reports)

- This folder is the answer key. Nothing here is ever ingested into the corpus, copied into `data/` or seeds, or pasted into prompts outside evaluation code.
- Write and change cases with the `/case` skill. Every label cites the provision or example that settles it, or is `legally_ambiguous`. The user approves every label.
- `eval/split.json` never changes after its first commit (INIT › Benchmark isolation 1).
- After tag `labels-v1`, every change under `eval/cases/` needs an entry in `eval/LABEL_CHANGES.md`.
- `eval/appliedai/` holds the appliedAI sources and extraction, under CC BY 4.0 (decision 002). Anything that quotes or shows its texts credits "appliedAI Institute for Europe gGmbH" (see its `SOURCE.md`). `eval/private/` is gitignored, for local-only files.
- Reports in `eval/reports/` quote numbers only from stored runs (with a run_id), never from memory.
