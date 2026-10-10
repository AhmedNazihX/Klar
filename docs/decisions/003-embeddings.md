# 003 · Embeddings: Qwen3-Embedding-8B at 1536 dimensions, query instruction under review

- **Date:** 2026-10-08 (measured); accepted 2026-10-09
- **Story:** X1a (docs/BACKLOG.md); feeds X1b (search tuning and the relevance cut-off)
- **Status:** accepted 2026-10-09, option B; X1b's search tuning, cut-off and exact references are at the end
  (2026-10-10). Option B: one model (Qwen3-Embedding-8B, 1536, Nebius) with a query side that
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

## X1b: search tuning, the relevance cut-off and exact references (2026-10-10)
Status: done by story X1b; the values are in code and settings. Measured with the accepted arm (Qwen3 1536):
Annex descriptions without an instruction, Q&A questions with the "governs it" text, as X1a did.

### Ranking (`aiact/retrieval/search.py`, `SearchTuning`)
`uv run aiact evaluate embeddings --arm qwen3-1536 --set annex_match --instruction "" …` and `--set qa`, with
the new options `--keyword-weight`, `--rrf-k`, `--max-term-share` and `--annex-points-only/--with-annex-containers`.
Top 5, as in the table above (R = strict recall, P = context precision).

| Keyword weight | RRF_K | Annex containers | Annex R / P | Annex R en / de | Q&A R / P | Q&A R en / de | Runs (annex, qa) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 | 60 | ranked (C6) | 0.312 / 0.255 | 0.333 / 0.286 | 0.753 / 0.540 | 0.775 / 0.704 | efafb418, 664c5833 |
| 0 | 60 | ranked | 0.396 / 0.363 | | 0.851 / 0.759 | | bf9cc6f8, 871161d5 |
| 1 | 60 | ranked | 0.271 / 0.190 | | 0.580 / 0.449 | | 0be0c116, 1d2dd41a |
| 0.1 | 10 | ranked | 0.396 / 0.363 | | 0.851 / 0.764 | | 6d12822d, cbd4e511 |
| 0.5 | 60 | skipped | 0.688 / 0.470 | | 0.753 / 0.542 | | abaf406a, 205c6e59 |
| **0.1** | **10** | **skipped** | **0.708 / 0.630** | **0.630 / 0.810** | **0.851 / 0.754** | **0.833 / 0.889** | 18821f14, bfe066f2 |
| 0 | 10 | skipped | 0.708 / 0.630 | | 0.851 / 0.777 | | 53c595f1, c351e0ea |
| 0.25 | 10 | skipped | 0.708 / 0.599 | | 0.851 / 0.757 | | d35c213a, 42e380b1 |
| 0.1 | 20 | skipped | 0.708 / 0.602 | | 0.851 / 0.754 | | e86f2a0a, 63b52135 |
| 0.1 | 30 | skipped | 0.708 / 0.601 | | 0.851 / 0.720 | | 40712be5, 9c39c268 |
| 0.5 | 5 | skipped | 0.729 / 0.599 | | 0.868 / 0.741 | | 75bae7d5, cb3b471a |

`MAX_TERM_SHARE` 0.01 and 0.1 rank exactly as 0.05 at the chosen weight (caa1b329, 12accaa4; a7408e9a,
eee9e6d8). With the chosen values, the Annex set searched with the "governs it" text (the MCP path) has strict
recall 0.583 (ad31ccae; X1a: 0.250). Each run's commit is in `eval_runs.git_sha` (55b3504 for most; the
embeddings code was the same from f4d9c60 on). The eight runs at 36f9dbc and 1b61703a are **superseded**: that
commit still pinned a whole annex named in passing (below). The Q&A baseline is 0.753, not X1a's 0.718
(67308d21), because the exact-reference rule finds `art:6:3` for qa-en-06, which names it.

- **The keyword arm only ever cost recall.** Every weight from 0 up lowered both sets (1.0: Q&A 0.580). The
  meaning arm carries the ranking; the keyword arm now breaks ties between close meaning-arm ranks
  (`KEYWORD_WEIGHT` 0.1, `RRF_K` 10) and still gives `found` its `keyword_idf`. From 0 to 0.25 and `RRF_K` 10
  to 30 recall is flat; 0.1 / 10 sits in the middle of that plateau. The single best point (0.5 / 5: one more
  Annex item, half a Q&A item) sits next to a steep drop (0.5 / 60) and is not taken: on 48 and 29 items that
  is one item, inside the noise.
- **Annex points rank on their own** (`skips_annex_containers`): an annex row with points under it (the whole
  annex, an Annex III area, an Annex I section) is left out of both ranked arms. With it in, the area row
  outranked its point in 15 of 48 descriptions and `distinct_units` then hid the point. This is X1a's
  strict-vs-lenient gap: strict recall goes from 0.396 to 0.708 and now equals lenient recall. Q&A recall is
  unchanged (0.851), precision drops 0.01. Articles keep their parent rows: a whole article holds the paragraph
  a question needs (V6's rule credits it), and taking leaves only there too cost Q&A recall in the
  exploration (0.718 to 0.425 at the old weights; not stored).
- `CANDIDATES` (50), `MIN_COMMON_ROWS` (50) and `MAX_TERM_SHARE` (0.05) stay.
- German now does better than English on Annex matching (0.810 vs 0.630). The English misses are mostly Annex I
  machinery and vehicle items, whose descriptions don't name the product legislation.
- The C6 cases still pass: Annex III 5(b) is found in the top 5 (EN) and top 10 (DE) by the recorded tests.

### Relevance cut-off (`SEARCH_MAX_DISTANCE` 0.30, `SEARCH_MIN_KEYWORD_IDF` 24)
`uv run aiact evaluate search-cutoff` (`aiact/eval/experiments/search_cutoff.py`), run **9d90bb41** at
a650381, $0.000135. It searches what Q&A and MCP search (the "governs it" text, the whole corpus) with 100
probes: the 29 answerable Q&A questions, the 48 Annex descriptions, B7's 9 unanswerable questions, and 14
off-topic strings (8 EN, 6 DE, in the module). For each it stores the best meaning-arm similarity, the best
keyword hit's summed IDF, whether it names a provision, the real `found` under the chosen settings (it matches
the sweep on all 100), and for answerable items the recall in the top 5 at each cut-off from 0.20 to 0.40.

Best similarity and best keyword IDF, [min, median, max]:

| Probes | n | Similarity | Keyword IDF |
| --- | --- | --- | --- |
| answerable (EN 20, DE 9) | 29 | 0.747 / 0.803 / 0.880 (DE min 0.747, EN min 0.763) | 0 / 10.6 / 29.4 |
| Annex descriptions (EN 27, DE 21) | 48 | 0.655 / 0.723 / 0.799 (DE 0.655 / 0.719 / 0.775) | 14.9 / 26.4 / 83.2 |
| unanswerable: other law (EN 4, DE 2) | 6 | 0.560 / 0.681 / 0.783 | 7.1 / 14.5 / 21.3 |
| unanswerable: national law (DE) | 1 | 0.700 (0.6999) | 15.3 |
| unanswerable: off topic (EN 1, DE 1) | 2 | 0.521, 0.667 | 8.0, 10.7 |
| off-topic strings (EN 8, DE 6) | 14 | 0.430 / 0.610 / 0.732 | 0 / 6.7 / 11.0 |

- **The cut-off: 0.30** (a hit counts at similarity 0.70 or more). It is the smallest cut-off at which recall
  in the top 5 stays at its uncut value, 0.851 (0.29: 0.839; 0.26: 0.805; a cut-off drops low-ranked required
  provisions before it makes a question unfound). Every answerable question stays found (lowest 0.747, German).
  Rejected: 7 of 9 unanswerable questions and 13 of 14 off-topic strings. Found anyway: qa-none-en-04 (DSA
  systemic risk, 0.783, close to the Act's own systemic-risk wording), qa-none-en-05 (Product Liability
  Directive, the near-topic hard negative, 0.720) and "asdf qwerty zxcv" (0.732). The national-law item sits at
  0.6999, so the margin is thin; 0.31 would find it.
- **The keyword rule: 24.** C8's 9 let almost every unanswerable question through: summed IDF grows with the
  query's length, and their best keyword hits reach 21.3. At 24 keywords never make an unanswerable or
  off-topic probe found, and they rescue the long descriptions whose best hit is under 0.70 but whose rare words
  match one row well (36 of 48 descriptions pass on similarity, 42 with the rule). A long off-topic text could
  pass it; none of the probes does.
- **Descriptions are the weak spot.** 6 of 48 Annex descriptions stay unfound, all German (0.676–0.700). The
  engine searches without a cut-off, so classification is not affected; a long German description pasted into
  Q&A or MCP search can get "nothing relevant". One cut-off can't serve both: 0.32 finds 47 of 48 but lets a
  third unanswerable question through.
- The sets are small (29, 9 and 14 negatives): a cut-off between 0.29 and 0.31 fits them equally; one
  item moves the shares by 3 to 11 points. Query vectors from the provider vary in the third decimal between
  runs (run a221b495, same probes, had 43 of 48 descriptions found).

### Exact references (`aiact/retrieval/references.py`)
"Article 50", "Art. 6(3)", "Annex III point 5(b)", "recital 27", "Artikel 26 Absatz 2", "Anhang III Nr. 5
Buchstabe b", "Erwägungsgrund 27" are read as provision ids. Search looks them up by id (a third arm, under the
same version, date, language and held-out filters) and puts them first in the order named; such a hit makes
`found` true. C8 found that the keyword arm can't find them (English "Article 50" has no keyword hit). In
the exploration each of eight reference probes (EN and DE) returned its provision first. A whole annex ("Annex III", "Hochrisiko-Systeme nach Anhang III") is **not** a reference: four Q&A
questions name it as a category, and pinning its whole text first crowded out the point that answers them. A
German Unterabsatz stops the reference at the paragraph (the ids put such points under `sub<n>` only where a
list restarts). Of the benchmark sets, only qa-en-06 names a provision ("Article 6(3)", required, now found).

### Not done here
- **The per-job query side** (no instruction for description searches) is not wired. Inside the engine no
  search does Annex matching: the engine looks every Annex point up (E5) and searches only the guidelines,
  where no labelled set measures the instruction. Q&A and MCP keep the "governs it" text. Wire it only with a
  guideline-retrieval measure behind it.
- **The engine's guideline searches now rank with the new constants** (keyword weight 0.1, `RRF_K` 10; the
  annex rule doesn't touch guidelines). Their recorded replays are unaffected; the next benchmark run shows the
  effect.
- **The RAGAS re-run** (V6) against c358b1e3 (`provision_recall` 0.598) was not run: it is paid
  (`uv run aiact evaluate ragas`, about $0.22 per arm on the Q&A set; V6's earlier runs cost $0.45–0.67). The
  free metric it is tied to, Q&A recall in the top 5, went from 0.718 (X1a) to 0.851 (bfe066f2).
