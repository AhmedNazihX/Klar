# Final evaluation (W1)

Numbers below are quoted from stored runs (`eval_runs` / `eval_case_results`) by run_id,
via `aiact evaluate report`. Classifications are guidance, not legal advice.

Status: draft. The build froze when W1 started (decision 024), at commit `6f5fa50`. The two full runs
are pending; this file holds their plan until the stored runs fill it.

## Plan of the two full runs

Budget: $15 OpenRouter for both full runs together (user, 2026-10-15). Each run's `--max-cost-usd`
stops new cases from starting; cases already in flight (concurrency 4) still finish, so a run can end
slightly above its cap. The caps are sized from the cost per case of the V8, V9 and V10b runs; the
spend is quoted here from the stored runs once they exist.

### Full run 1: every set, classifier and mode INIT › Metrics needs

| # | Command (`aiact evaluate …`) | Cases | Metric it serves | Cap |
| --- | --- | ---: | --- | ---: |
| 1 | `run --set commission_b --classifier engine --exclude-mode heldout` | 153 | headline accuracy, false low risk, Annex point, role, uncertain outcomes, citation existence | $1.50 |
| 2 | `run --set commission_b --classifier engine --exclude-mode all` | 153 | held-out vs in-corpus gap | $1.50 |
| 3 | `run --set own --classifier engine --exclude-mode heldout` | 88 | development-case accuracy (decision 018) and the same metrics | $0.75 |
| 4 | `run --set own --classifier engine --exclude-mode all` | 88 | gap on the own cases | $0.75 |
| 5 | `run --set soft_pairs --classifier engine` | 24 | downgrade rate, without key-fact answers | $0.25 |
| 6 | `run --set consistency --classifier engine` | 30 | consistency | $0.30 |
| 7 | `run --set annex_match --classifier engine` | 48 | Annex point accuracy on Annex matching | $0.50 |
| 8 | `run --cases-from-draw --classifier engine` | 25 | head-to-head engine column (decision 036) | $0.25 |
| 9 | `run --set appliedai --classifier engine` | 106 | second benchmark | $1.05 |
| 10 | `run --set academic --classifier engine` | 339 | extra check | $3.00 |
| 11 | `run --set commission_b --classifier baseline_luna` | 153 | baseline | $0.17 |
| 12 | `run --set own --classifier baseline_luna` | 88 | baseline | $0.07 |
| 13 | `run --set commission_b --classifier baseline_jev` | 153 | baseline | $0.01 |
| 14 | `run --set own --classifier baseline_jev` | 88 | baseline | $0.01 |
| 15 | `ragas` | 29 | RAGAS context precision, recall, faithfulness on the Q&A set | $0.25 |
| 16 | `embeddings --arm qwen3-1536 --set annex_match --set qa` | 77 | retrieval precision and recall on Annex matching and Q&A | $0.01 |
| 17 | `run --set soft_pairs --classifier engine --answers-from <run 5>` | 24 | downgrade rate with key-fact answers (decision 019) | $0.25 |

Run 1 caps: $10.62 in total.
Judged passes after run 1 (`judged <run_id>`, a dry run first): runs 1 and 3 (citation support,
evidence tags) and run 15 (Q&A support), caps $0.75, $0.40 and $0.03.

### Full run 2

Planned after run 1's spend is known, sized to the rest of the $15: the sets whose numbers vary from
run to run (runs 1, 3, 5, 6, 7, 15 and 17 above, then their judged passes).
