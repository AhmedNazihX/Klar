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
arm and stores one `eval_runs` row per arm and set (benchmarks `embedding_annex_match`, `embedding_qa`):
- **Annex matching** (X0, 48 items: 27 EN, 21 DE): the description, law only,
  no distance cut-off. A hit counts only when it is a labelled Annex III point or lies under it (an area or the
  whole annex doesn't pin the point); any one accepted point is full recall.
- **Q&A** (B7, the 29 answerable items: 20 EN, 9 DE): the question over the whole corpus, as Q&A searches. A hit counts when
  it is a required provision, under one or above one, as V6's `provision_recall` counts it.
- **Metrics:** RAGAS's context precision (average precision over the ranked top 5) and context recall (share of
  targets in the top 5), with the relevance verdict taken from provision ids instead of a judge model (RAGAS's
  ID-based variants). They are exact and cost only the query embeddings. Also stored: the reciprocal rank of
  the first relevant hit in the top 20, and the top hit's cosine similarity.
- **Check:** Q&A recall for the default arm and instruction is 0.598, the same value as V6's model-free
  `provision_recall` in its RAGAS baseline run c358b1e3 (same items, same top 5, same rule).

## Results (top 5)
P = context precision, R = context recall, RR = mean reciprocal rank (top 20), S = mean top-hit cosine.

| Arm | Query instruction | Annex P / R / RR | Annex R en / de | Q&A P / R / RR | Q&A R en / de | Runs (annex, qa) |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3 1536 | current (placeholder) | 0.153 / 0.208 / 0.159 | 0.185 / 0.238 | 0.486 / 0.598 / 0.543 | 0.550 / 0.704 | d234f3c7, e0861fa5 |
| Qwen3 1536 | none | 0.255 / 0.312 / 0.260 | 0.333 / 0.286 | 0.363 / 0.425 / 0.414 | 0.375 / 0.537 | 622343d5, 7ffbb4ad |
| Qwen3 1536 | "governs it" (below) | 0.174 / 0.250 / 0.180 | 0.185 / 0.333 | 0.504 / 0.718 / 0.541 | 0.725 / 0.704 | 1eb719f8, 96d717ee |
| Qwen3 1024 | current (placeholder) | 0.145 / 0.208 / 0.155 | 0.222 / 0.190 | 0.499 / 0.632 / 0.550 | 0.600 / 0.704 | 50c35f8a, ca9e5699 |
| Qwen3 1024 | "governs it" | 0.167 / 0.208 / 0.176 | 0.185 / 0.238 | 0.496 / 0.701 / 0.538 | 0.700 / 0.704 | fc6dbf57, bfd90f0f |
| OpenAI 3-large 1536 | none (not instruction-aware) | pending | | pending | | |

Run ids are the first 8 characters of `eval_runs.id`, all at commit c884764. The instructions:
- current: "Given a description of an AI system or a question about the EU AI Act, retrieve the provisions of the AI
  Act that apply"
- "governs it": "Given a description of an AI system or a question about the EU AI Act, retrieve the article, Annex point
  or recital of the AI Act that governs it"

Cost: the query embeddings of all ten runs came to under $0.001; embedding the corpus for Qwen3 1024 (about 1.3
million tokens, 9,083 rows) about $0.013.

Pending (paid, needs the user's go-ahead):
- the OpenAI arm: `uv run aiact corpus embed --model openai3l --dims 1536` (about 1.3 million tokens at $0.13
  per million, about $0.17), then `uv run aiact evaluate embeddings --arm openai3l-1536` (under $0.01);
- the judged RAGAS context precision and recall (and faithfulness) on the Q&A set per arm:
  `uv run aiact evaluate ragas --arm <arm>`, about $0.0077 per item, 29 items, about $0.22 per arm, $0.67 for
  all three.

## Reading
- **1536 vs 1024:** level. Annex recall is 0.208 for both; Q&A recall differs by 0.03 either way depending on
  the instruction (one item in 29 is 0.034). 1024 brings nothing measurable at 9,083 rows, where search is an
  exact scan of about 15 ms either way (C6), so the default stays at **1536**, which needs no re-embedding.
- **The instruction matters more than the size.** Without one, Annex matching gains (0.208 to 0.312, five
  items of 48) and Q&A loses (0.598 to 0.425). The "governs it" text is better than the placeholder on both
  sets at 1536 (Annex 0.208 to 0.250, two items; Q&A 0.598 to 0.718, about three and a half items' worth of
  provisions). These gaps are a few items each on small sets, so they show a direction, not a settled value.
- **Annex matching is weak for every arm:** the top 5 are mostly long parent rows (the whole of Annex III,
  Art. 3, Art. 5, recitals): of the 240 top-5 hits of run d234f3c7, 159 are articles, 47 recitals and 33 Annex
  III rows, 15 of those the annex as a whole (in 15 of the 48 searches). Search keeps the better-ranked of a parent and its children
  (`distinct_units`), so the whole annex ranked 5th hides every point in it. This is a search matter for X1b
  (parent rows, `doc_keys`, the keyword weight), not an embedding one. The engine is not affected: it looks up
  every Annex III point itself (E5) and searches only the guidelines.

## Decision (proposed)
- Keep **Qwen3-Embedding-8B on Nebius at 1536 dimensions** unless the OpenAI arm, once run, beats it clearly on
  both sets.
- The query instruction is the user's choice, below. If it changes, the corpus does *not* need re-embedding
  (documents get no instruction), but `tests/recordings/db/test_search_ai_act/` must be re-recorded; the
  isolation cache (`eval/isolation/embeddings.json`) embeds documents without an instruction and stays valid.

## Consequences
- `EMBEDDING_QUERY_INSTRUCTION` (default in `aiact/settings.py`) sets the instruction; `OpenRouterEmbeddings`
  sends queries without one when it is empty (the OpenAI arm).
- Partial HNSW indexes exist for `qwen/qwen3-embedding-8b`/1024 and `openai/text-embedding-3-large`/1536
  (migration `20261008012443_embedding_arm_indexes.sql`); the 1024 vectors stay in `provision_embeddings`,
  apart from the default arm.
- If the arm changes, B13's isolation cosine limit 0.9 (`EMBEDDING_COSINE_LIMIT`, measured on Qwen3) must be
  re-measured, `eval/isolation/embeddings.json` regenerated and the corpus re-embedded.
