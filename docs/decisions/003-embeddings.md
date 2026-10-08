# 003 · Embeddings: Qwen3-Embedding-8B at 1536 dimensions, query instruction under review

- **Date:** 2026-10-08 (measured); accepted 2026-10-09
- **Story:** X1a (docs/BACKLOG.md); feeds X1b (search tuning and the relevance cut-off)
- **Status:** accepted 2026-10-09, option B: one model (Qwen3-Embedding-8B, 1536, Nebius) with a query side that
  differs per job (see Decision). The OpenAI arm is measured with the free metrics; the judged RAGAS runs were
  not run (user decision 2026-10-09; they can run later).

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
| OpenAI 3-large 1536 | none (not instruction-aware) | 0.284 / 0.583 / 0.688 / 0.299 | 0.481 / 0.714 | 0.593 / 0.810 | 0.194 / 0.253 / 0.240 | 0.175 / 0.426 | dabf3f19, 80bf1fd3 |

Judged RAGAS context precision, recall and faithfulness (`uv run aiact evaluate ragas --arm <arm>`): **not run
(user decision 2026-10-09; can run later)**, for every arm. The free metrics above decide this record.

Run ids are the first 8 characters of `eval_runs.id`. The Qwen3 runs are at commit 690109b with a clean tree;
the OpenAI runs came afterwards (full ids dabf3f19-d624-4f96-bd95-2c8493a01362 and
80bf1fd3-c58a-4bc4-8572-008213d6457c). Ten earlier runs
at c884764 (d234f3c7, e0861fa5, 622343d5, 7ffbb4ad, 1eb719f8, 96d717ee, 50c35f8a, ca9e5699, fc6dbf57, bfd90f0f)
are **superseded**: their Q&A rule also credited a hit under a required provision, and they have no lenient
recall. The instructions:
- current: "Given a description of an AI system or a question about the EU AI Act, retrieve the provisions of the AI
  Act that apply"
- "governs it": "Given a description of an AI system or a question about the EU AI Act, retrieve the article, Annex point
  or recital of the AI Act that governs it"

Cost, on the embedding API (OpenRouter), not counting the coding agents' own token use:
- the query embeddings of the twenty Qwen3 runs: about $0.001; the corpus for Qwen3 1024 (about 1.3 million
  tokens, 9,083 rows): about $0.013;
- the OpenAI arm: embedding the corpus (`uv run aiact corpus embed --model openai3l --dims 1536`) took 5,682
  texts for 9,081 rows, 1,209,546 tokens, $0.157241; two texts over 24,000 characters were not embedded (the
  omnibus `art:1` rows that search excludes); the Annex run cost $0.000893 and the Q&A run $0.000095.

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
  articles (Art. 3, Art. 5, Art. 6 and the like), 46 recitals, 16 a whole annex (15 Annex III, 1 Annex VIII), 7 an area or
  section, and 12 a point. This is a search matter for X1b (parent rows, `doc_keys`, the keyword weight), not
  an embedding one. The engine is not affected: it looks up every Annex point itself (E5) and searches only
  the guidelines.

- **OpenAI text-embedding-3-large (1536) wins Annex matching and loses Q&A badly.**
  - Annex matching: 0.583 strict and 0.688 lenient, against 0.250 / 0.396 for Qwen3 with the "governs it"
    text and 0.312 / 0.625 for Qwen3 with no instruction. On strict recall OpenAI finds 28 of 48 items, Qwen3
    without an instruction 15; on lenient recall the lead over Qwen3 without an instruction is 0.063 (three
    items), so most of the strict gap is the parent-row effect above.
  - Q&A: 0.253 context recall, against 0.718 for Qwen3 "governs it" and 0.391 for Qwen3 with no instruction.
    German questions fare better (0.426) than English (0.175).
  - Qwen3 with no instruction reaches 0.625 lenient Annex recall; Qwen3 "governs it" is the best on Q&A (0.718).

## Decision (accepted 2026-10-09, option B)
- **One model: Qwen3-Embedding-8B on Nebius at 1536 dimensions**, with a query side that differs per job:
  - Q&A and MCP searches use the "governs it" instruction. `EMBEDDING_QUERY_INSTRUCTION` defaults to it
    (`aiact/settings.py`).
  - Description searches (Annex matching inside the engine) use no instruction. That per-job split is not built
    here: **X1b** wires and measures it, together with the search matters above.
- **A two-model setup was rejected** (OpenAI for descriptions, Qwen3 for questions): it needs two vendors and a
  US provider for descriptions, against decision 005's EU pinning, for a gain that is mostly the
  strict-vs-lenient parent-row effect.
- **The OpenAI vectors stay** in `provision_embeddings` (their partial index is in migration
  `20261008012443_embedding_arm_indexes.sql`). Rebuilding them would cost about $0.16 (measured above), so
  deleting them saves nothing worth the loss.
- The judged RAGAS runs were skipped by the user's decision. Run them later with
  `uv run aiact evaluate ragas --arm <arm>` (about $0.22 per arm on the Q&A set).
- Changing the default instruction does not need a corpus re-embedding (documents get no instruction), but
  `tests/recordings/db/test_search_ai_act/` must be re-recorded: its two cassettes hold the old instruction.
  The isolation cache (`eval/isolation/embeddings.json`) embeds benchmark texts as documents, without an
  instruction, so it stays valid, and B13's cosine limit 0.9 (`EMBEDDING_COSINE_LIMIT`) needs no change: the
  model is the same and the limit is measured on document-to-document cosines.

## Consequences
- `EMBEDDING_QUERY_INSTRUCTION` (default in `aiact/settings.py`) sets the instruction; `OpenRouterEmbeddings`
  sends queries without one when it is empty (the OpenAI arm).
- Partial HNSW indexes exist for `qwen/qwen3-embedding-8b`/1024 and `openai/text-embedding-3-large`/1536
  (migration `20261008012443_embedding_arm_indexes.sql`); the 1024 vectors stay in `provision_embeddings`,
  apart from the default arm.
- If the arm changes, B13's isolation cosine limit 0.9 (`EMBEDDING_COSINE_LIMIT`, measured on Qwen3) must be
  re-measured, `eval/isolation/embeddings.json` regenerated and the corpus re-embedded.
