# Limitations

The full list behind the README's Limitations section. Each item names the decision or report it comes from.

## Labels and benchmark

- **No external legal review.** The labels of the own test cases are the author's, checked by a second model
  (Claude Haiku 4.5) whose disagreements were investigated; that filter catches mistakes and isn't validation.
- **Labels were frozen per category, not before the engine.** Each own-case category's labels were frozen before
  the engine step that replays it, and the whole set was tagged `labels-v1` later; every change after a freeze is
  logged in `eval/LABEL_CHANGES.md` (decision 017).
- **Own cases are development cases.** The engine's steps were tuned against them, so their accuracy is reported
  as "cases the engine was developed against"; the held-out Commission examples and the academic benchmark carry
  the headline (decision 018).
- **The headline benchmark rests on draft guidance.** It is built from the Commission's draft high-risk guidelines
  of 19 May 2026; if they are finalised, the benchmark stays frozen on the draft (decision 021).
- **On Commission Pile B the engine over-classifies rather than under-classifies.** None of run 1's 46 misses
  with a result put a high-risk or prohibited system lower; 4 answered "not an AI system" where the label is
  minimal (the same duties). 27 of its 52 misses came from taking the stricter reading
  when a step was unsure (decision 010's working assumption). Source: eval/reports/final.md › Later analysis
  (2026-10-15), an AI agent's reading of the stored steps, not reviewed case by case.
- **The problem wasn't validated with users.** The evidence comes from secondary sources; no user interviews or
  tests were run.

## The final evaluation

From [eval/reports/final.md](../eval/reports/final.md) › Limitations, where each figure names its run.

- **Run-to-run spread.** Run 2 repeats the varying sets on the same build, cases and settings; the differences
  between the two runs (for example the headline 65.8% and 60.5%) come from run-to-run variance.
- **False low risks on repeated sets.** Run 2 had false low risks where run 1 had none on the same sets:
  Commission Pile B 1.7% (1/59) and Annex matching 2.1% (1/47); on the soft pairs with key-fact answers it had
  8.7% (2/23) against run 1's 4.3% (1/23).
- **Citation support is low,** from 14.5% (97/669) to 21.6% (65/301) as judged. Why is not analysed, and the
  judge's share of wrong "not supported" verdicts on these runs is unknown.
- **No hand-reviewed sample of the judge's verdicts.** The judge was validated against hand-labelled items before
  (decision 006), but INIT's manual sample of the final runs' verdicts was dropped (user, 2026-10-15).
- **Output-cap cut-offs.** A reply cut off at the output cap is asked once more, and one cut off twice can become
  a failed case; the counts don't show how many failed cases came from them.
- **RAGAS faithfulness about 0.80** on the Q&A set, below its context recall: some answers state more than the
  retrieved text supports, by RAGAS's own measure.
- **Tool-call correctness** was read for 2 of the 4 planned runs, both own-case runs; the LangSmith reads of the
  Pile B headline runs did not finish, so there is no figure on them.

## Legal reading

- **The original-text toggle covers the class, not the duties.** Under the original text the class and route come
  from the original provisions and only the Art. 113 route dates change (2 August 2026 for Annex III, 2 August 2027
  for Annex I); the duty list stays the amended text's, with a notice saying so (decision 020 and its addendum).
- **Art. 111.** Art. 111(1) (components of the large-scale IT systems in Annex X) isn't modelled. The per-product
  caveat on Art. 111(2) results rests on the New Legislative Framework reading (the Commission's Blue Guide), which
  isn't in the corpus. The 2 August 2030 date for public-authority systems follows the article's "providers and
  deployers" over the English recital 177's "operators" (decision 022).
- **Art. 26(8)'s language versions differ.** The English text reads "public authorities, or Union institutions…",
  the German only "Organe, Einrichtungen oder sonstige Stellen der Union". Klar's German condition follows the
  English ("Sie sind eine Behörde oder …"), so it matches whenever the duty is shown (user, 2026-10-12).
- **The EU link is read from the description only.** The company profile is not an input to classification
  (decision 026 item 7): it drives the SME notes and pre-fills the establishment answers, but whether the system
  reaches the EU comes from what the description says.
- **The simplified technical documentation form** for SMEs and small mid-caps isn't published yet, so they get the
  full Annex IV skeleton with a note.
- **A provider refusal gives no class.** When both models' filters block a check, a person must review the system
  (decisions 029, 030, 033).

## The app

- **Results saved before the German duty conditions** (story P11) keep English duty conditions and fact sentences
  on German screens until the tool is classified again in German; the reports print the German conditions (user,
  2026-10-12).
- **Q&A history** is kept only in the browser session; closing it loses the questions (decision 026).
- **Vendor letters are drafts** built only from the result's facts (decision 026).
- **No prompt-injection framing.** The engine prompts don't tell the model to treat the description as untrusted,
  and there are no injection test cases. The guards are the rate limits, the input caps, the strict output
  schemas, the fixed check order and the citation check (review with the user, 2026-10-15).
- **No app-level spending cap.** The OpenRouter key's own spending limit is the backstop (review with the user,
  2026-10-15).
- **The embedding host's region is unconfirmed.** Nebius was chosen as an EU host, but OpenRouter gives its
  endpoint no region tag (decision 005); the Privacy page says so.
- **The hosted database is on the Free plan,** which pauses after 7 idle days: open the app before a demo (decision
  034).
