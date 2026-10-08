# 003 · Embeddings: Qwen3-Embedding-8B at 1536 dimensions, query instruction under review

- **Date:** 2026-10-08
- **Story:** X1a (docs/BACKLOG.md); feeds X1b (search tuning and the relevance cut-off)
- **Status:** proposed. The Qwen3 numbers below are measured. The OpenAI arm and the judged RAGAS runs are
  still to run (paid, above the story's cost cap), and the query instruction is the user's choice.

## Question
INIT › Tech stack › Embeddings picks Qwen3-Embedding-8B (Nebius, EU) at 1536 dimensions with a fixed query-side
task instruction, and asks week one to confirm it: RAGAS context recall on the Annex-matching and Q&A sets,
against OpenAI text-embedding-3-large, and whether 1024 dimensions holds up as well as 1536 (INIT › Open
questions). The query instruction was a placeholder (`aiact/llm/embeddings.py`, C4); it is now the setting
`EMBEDDING_QUERY_INSTRUCTION`.

## How it was measured
`uv run aiact evaluate embeddings` (`backend/aiact/eval/experiments/embeddings.py`) searches every item with one
arm and stores one `eval_runs` row per arm and set (benchmarks `embedding_annex_match`, `embedding_qa`). No
search applies a distance cut-off.
- **Annex matching** (X0, 48 items: 27 EN, 21 DE; 9 accept an Annex I point, one of them also Annex III 5(d)): the
  description, law only. A hit counts only when it is a labelled Annex I or III point or lies under it; any one
  accepted point is full recall.
- **Q&A** (B7, the 29 answerable items: 20 EN, 9 DE): the question over the whole corpus, as Q&A searches. A hit
  counts by V6's rule (`ragas_metrics.covers`): it is a required provision or an ancestor of one, whose text
  includes its children's (C1); never a descendant. Recall is V6's `provision_recall` itself.
- **Metrics:**
  - Context precision uses the formula of RAGAS's judged context precision (average precision over the ranked
    top 5), with the relevance verdict taken from provision ids instead of a judge model. RAGAS's own ID-based
    precision is plain set precision and ignores the order.
  - Context recall is ID-based recall (share of targets in the top 5) with the hierarchy rules above, and the
    any-one-point rule for Annex items.
  - Both are exact and cost only the query embeddings. Also stored: the reciprocal rank of the first relevant hit
    in the top 20, and the top hit's cosine similarity.
- **Lenient Annex recall.** Search keeps the better-ranked of a parent row and its children
  (`distinct_units`). So when a point's area or section row (`annex:III:4`, `annex:I:A`) outranks the point, the
  point is dropped although the area's text contains it, and strict recall scores 0. This depends on how an arm
  ranks long parent rows, so it is not neutral between arms. `annex_recall_lenient` also accepts the point's own
  area or section (never the whole annex) and shows how much of the gap that is.
- **Check:** Q&A recall for the default arm and instruction is 0.598, the same value as V6's `provision_recall`
  in its RAGAS baseline run c358b1e3: the same function on the same items and top 5.

## Results (top 5)
P = context precision, R = context recall (strict), L = lenient Annex recall, RR = mean reciprocal rank (top 20).

| Arm | Query instruction | Annex P / R / L / RR | Annex R en / de | Annex L en / de | Q&A P / R / RR | Q&A R en / de | Runs (annex, qa) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3 1536 | current (placeholder) | 0.153 / 0.208 / 0.354 / 0.159 | 0.185 / 0.238 | 0.259 / 0.476 | 0.486 / 0.598 / 0.543 | 0.550 / 0.704 | 7a22e08e, 47aeca1c |
| Qwen3 1536 | none | 0.255 / 0.312 / 0.625 / 0.259 | 0.333 / 0.286 | 0.667 / 0.571 | 0.346 / 0.391 / 0.394 | 0.325 / 0.537 | 0f8bfc58, 454ed4e8 |
| Qwen3 1536 | "governs it" (below) | 0.174 / 0.250 / 0.396 / 0.180 | 0.185 / 0.333 | 0.259 / 0.571 | 0.504 / 0.718 / 0.541 | 0.725 / 0.704 | f196a558, 67308d21 |
| Qwen3 1024 | current (placeholder) | 0.144 / 0.208 / 0.375 / 0.155 | 0.222 / 0.190 | 0.296 / 0.476 | 0.499 / 0.632 / 0.550 | 0.600 / 0.704 | 18641694, d6a9e118 |
| Qwen3 1024 | "governs it" | 0.167 / 0.208 / 0.396 / 0.178 | 0.185 / 0.238 | 0.296 / 0.524 | 0.496 / 0.701 / 0.538 | 0.700 / 0.704 | 47b92584, 2f21c0b4 |
| OpenAI 3-large 1536 | none (not instruction-aware) | pending | | | pending | | |

Run ids are the first 8 characters of `eval_runs.id`, all at commit 690109b with a clean tree. Ten earlier runs
at c884764 (d234f3c7, e0861fa5, 622343d5, 7ffbb4ad, 1eb719f8, 96d717ee, 50c35f8a, ca9e5699, fc6dbf57, bfd90f0f)
are **superseded**: their Q&A rule also credited a hit under a required provision, and they have no lenient
recall. The instructions:
- current: "Given a description of an AI system or a question about the EU AI Act, retrieve the provisions of the AI
  Act that apply"
- "governs it": "Given a description of an AI system or a question about the EU AI Act, retrieve the article, Annex point
  or recital of the AI Act that governs it"

Cost: the query embeddings of all twenty runs came to about $0.001. Embedding the corpus for Qwen3 1024 (about
1.3 million tokens, 9,083 rows) cost about $0.013.

Pending (paid, needs the user's go-ahead):
- the OpenAI arm: `uv run aiact corpus embed --model openai3l --dims 1536` (about 1.3 million tokens at $0.13
  per million, about $0.17), then `uv run aiact evaluate embeddings --arm openai3l-1536` (under $0.01);
- the judged RAGAS context precision and recall (and faithfulness) on the Q&A set per arm:
  `uv run aiact evaluate ragas --arm <arm>`, about $0.0077 per item, 29 items, about $0.22 per arm, $0.67 for
  all three. With `--arm`, search applies no distance cut-off.

## Reading
- **1536 vs 1024: level.** Strict Annex recall is 0.208 for both; lenient differs by one item. Q&A recall differs
  by 0.03 either way depending on the instruction (one item in 29 is 0.034). 1024 brings nothing measurable at
  9,083 rows, where search is an exact scan of about 15 ms either way (C6). So the default stays at **1536**,
  which needs no re-embedding.
- **The instruction matters more than the size, and it pulls the two sets apart.**
  - Without an instruction, Annex matching gains a lot: lenient 0.354 to 0.625 (13 items of 48), strict 0.208 to
    0.312. Q&A loses: 0.598 to 0.391.
  - The "governs it" text is better than the placeholder on both sets at 1536: Annex strict 0.208 to 0.250
    (two items), lenient 0.354 to 0.396; Q&A 0.598 to 0.718. It is still far below no instruction for
    descriptions.
  - A description and a question want different query sides. These gaps are a few items each on small sets,
    except the no-instruction Annex gain, which shows a direction rather than a settled value.
- **Strict Annex matching is weak for every arm**, and the gap between the strict and lenient columns is the
  confound above. The top 5 are mostly long parent rows. Of the 240 top-5 hits of run 7a22e08e: 159 are
  articles (Art. 3, Art. 5, Art. 6 and the like), 46 recitals, 15 the whole of Annex III or I, 7 an area or
  section, and 13 a point. This is a search matter for X1b (parent rows, `doc_keys`, the keyword weight), not
  an embedding one. The engine is not affected: it looks up every Annex point itself (E5) and searches only
  the guidelines.

## Decision (proposed)
- Keep **Qwen3-Embedding-8B on Nebius at 1536 dimensions** unless the OpenAI arm, once run, beats it clearly on
  both sets.
- Query instruction (the user's choice). The recommended option: set `EMBEDDING_QUERY_INSTRUCTION` to the "governs
  it" text, which beats the placeholder on both sets, and have X1b add a separate query side for system
  descriptions (no instruction, or one written for descriptions), measured with this command. The alternative is
  to keep one instruction for both.
- If the instruction changes, the corpus does *not* need re-embedding (documents get no instruction), but
  `tests/recordings/db/test_search_ai_act/` must be re-recorded. The isolation cache
  (`eval/isolation/embeddings.json`) embeds documents without an instruction and stays valid.

## Consequences
- `EMBEDDING_QUERY_INSTRUCTION` (default in `aiact/settings.py`) sets the instruction; `OpenRouterEmbeddings`
  sends queries without one when it is empty (the OpenAI arm).
- Partial HNSW indexes exist for `qwen/qwen3-embedding-8b`/1024 and `openai/text-embedding-3-large`/1536
  (migration `20261008012443_embedding_arm_indexes.sql`); the 1024 vectors stay in `provision_embeddings`,
  apart from the default arm.
- If the arm changes, B13's isolation cosine limit 0.9 (`EMBEDDING_COSINE_LIMIT`, measured on Qwen3) must be
  re-measured, `eval/isolation/embeddings.json` regenerated and the corpus re-embedded.
