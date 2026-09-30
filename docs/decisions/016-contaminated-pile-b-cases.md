# 016 · Two held-out examples are retold in the corpus: keep the passages, flag the cases

- **Date:** 2026-09-30
- **Story:** B13 (docs/BACKLOG.md); also affects B4, V8, W1
- **Status:** accepted (the user chose option (b) for both passages on 2026-09-30)

## Question
Decision 001 keeps the Commission's own prose around its examples in the corpus. B13 was asked to measure
the passages nearest to Pile B examples (INIT › Evaluation › Benchmark isolation). Two retrievable
paragraphs of the Annex III guidelines tell the same system as a held-out example and reach the same verdict.
A search for either example can then bring back the Commission's answer, so a correct result on those cases
may come from lookup rather than reasoning. The question was whether to hold the paragraphs out, flag the
cases, or accept them.

## The two passages
| Held-out example | Retrievable passage | What they share | 6-gram coverage | Longest run | Cosine |
| --- | --- | --- | --- | --- | --- |
| hr-ex-269 (7(c), not high-risk, Art. 6(3)(c); p. 130) | `guide:guide-high-risk-annex-iii:para:102` ("c) Detect decision-making patterns or deviations"; general Art. 6(3)(c) section) | Its "Example:" and "Assessment:" describe the same quality-assurance analysis of completed eligibility files, exempt under Art. 6(3)(c) | 0.318 | 10 words | 0.764 |
| hr-ex-031 (1(a), not high-risk, outside the use case; p. 27) | `guide:guide-high-risk-annex-iii:para:152` ("a) Subparagraphs 1 and 2 of Article 26(10) AI Act") | Retells the crime-scene analysis sentence by sentence, verdict included (closed dataset, not RBI, not high-risk) | 0.213 | 12 words | 0.847 |

Sources: `backend/aiact/eval/isolation.py` (B13, branch `story/B13-isolation-check-ci`, commit 2019fa1),
measured by the DoD verifier and re-measured by the committed code; the numbers are stored in
`eval/isolation/contaminated.json`, and `test_the_contaminated_overlaps_are_as_recorded` re-checks them. (The
worker's first report gave 0.375 / 12 words and 0.217 from a scratch script that didn't join hyphens.) Cosines are Qwen3-Embedding-8B/1536 (`eval/isolation/embeddings.json` against the
corpus vectors). Neither passage crosses B13's thresholds (6-gram coverage 0.5 for prose rows, cosine 0.9),
so the automatic check passes while both overlaps remain.

## Options
| Option | Effect on the corpus | Effect on the benchmark |
| --- | --- | --- |
| (a) Hold each paragraph out with its example (a C2/C3 tagging change) | Removes the main explanation of Art. 6(3)(c) (para 102) and the closed-dataset rule for biometrics and Art. 26(10) (para 152) for every case | The two cases stay clean |
| (b) Keep the paragraphs; flag the two cases as contaminated | Unchanged | The cases stay in the benchmark but are flagged; the headline is reported with and without them |
| (c) Accept them as they are | Unchanged | Two cases count at face value though the engine may have looked the answer up |

## Decision
Option (b) for both: paragraphs 102 and 152 stay retrievable, and the benchmark cases built from hr-ex-269
and hr-ex-031 are flagged as contaminated. Both paragraphs state general legal rules the engine needs for many
cases; flagging costs two cases and keeps the headline honest.

## Consequences
- **Contaminated list:** `hr-ex-269`, `hr-ex-031` (source example ids). Any benchmark case whose source is one
  of these is contaminated.
- **B4:** the rewritten cases from these two examples keep their `source_example_id`, so the eval code can find
  them; write them as usual (their verdicts stay as labelled).
- **V8 / W1 / the report:** report headline accuracy twice, over all held-out cases and without the
  contaminated ones; name the two cases and this record. The eval code reads the list from one place (a
  constant or a small file under `eval/`), not from this document.
- **B13:** the isolation check stays as it is; it records these two known overlaps rather than failing on them.
- **Revisit** if a later measurement (a lower threshold, sentence-level embeddings, or W0's refreshed
  guidelines) finds more passages this close, or if the flagged cases score clearly better than the rest.
