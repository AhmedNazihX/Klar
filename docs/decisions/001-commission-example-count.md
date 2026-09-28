# 001 · Commission high-risk examples: count and split mode

- **Date:** 2026-09-28
- **Story:** B2 (docs/BACKLOG.md)
- **Status:** proposed (waiting for the user to check the extraction against the PDFs)

## Question
How many worked examples do the draft high-risk guidelines (version 2026-05-19) contain, per area and verdict?
The count decides how the headline benchmark is isolated from retrieval. With about 40 or more examples they are
split into Pile A (stays in the corpus) and Pile B (removed from the corpus and scored). With fewer, every example
stays in the corpus and each run filters out the example a case was written from, which is leave-one-out
(INIT > Evaluation > Benchmark isolation 1–2; INIT > Open questions, "Count the worked examples").

## What counts as an example
The draft is published as three PDFs (ids in `data/manifest.yaml`). The rule below is mechanical so that C2 can
give each example the same `source_example_id` from the PDF alone, without reading `eval/`.

1. **Sources.**
   - `guide-high-risk-general`: this part has no examples.
   - `guide-high-risk-annex-i`: the named systems in paras. (43), (45), (46), (47) and (49), 12 in total.
     Para. (43) holds two systems: the gas-appliance optimiser, then the heating-schedule optimiser ("Conversely, …").
     Para. (49) is one example, the smart thermostat.
   - `guide-high-risk-annex-iii`: every list under a heading that begins "Practical example(s) of AI systems
     falling within / outside / within the use case but exempted …" (72 lists). Two more lists state a verdict
     without that heading, and they are counted too:
     - the cybersecurity list in section 3.2.1, which begins "Examples of AI systems used solely for cybersecurity
       purposes" (PDF page 41);
     - the list in para. (372) of section 3.6.7 (PDF pages 116–117).
2. **Unit.** Each top-level bullet ("–" or "-") is one example. A bullet with "o" sub-bullets counts once per
   sub-bullet, and its opening sentence is stored as `lead_in`. This happens twice in point 1(a): five
   verification systems and four presence-detection systems. The three lists printed without bullet markers
   (gas, heating, and electricity "within") count one example per paragraph, so electricity has two.
3. **Order and IDs.** Annex I examples come first, then Annex III, each in document order. IDs run from
   `hr-ex-001` to `hr-ex-307`.
4. **Verdict.**
   - Annex III: a "within" heading gives `high`. An "outside" or "exempted by the filter" heading gives `not_high`,
     and `basis` records which of the two (`outside_use_case` or `art_6_3_filter`).
   - Annex I: a safety component (paras. 43, 45, 46) gives `high`, and paras. 43, 47 and 49 give `not_high`. The
     guidelines settle only the safety-component question. High-risk under Art. 6(1) also needs a third-party
     conformity assessment under the sectoral act, so all 12 Annex I rows carry a review flag.
5. **Not counted.** Illustrations inside the running text are not counted, because they sit under no verdict
   heading. They stay in the corpus in both modes. Where they are:
   - Annex III: the "Example:" boxes and "For example" passages in section 2 (PDF pages 7–15); the RBI search
     examples (pages 29–33); the IRB example (page 94); the customs example (page 103).
   - Annex I: the "Safety functions – indicative examples" list (PDF pages 6–7) and the generic smart-appliance
     statement in para. (48).
6. **Pages.** `page` is the physical PDF page. `printed_page` is the number printed on it, which is one lower in
   all three PDFs because the cover page carries no number.

## Counts
Recount: `jq -rs 'group_by(.area)[] | [.[0].area, (map(select(.verdict=="high"))|length), (map(select(.verdict=="not_high"))|length), length] | @tsv' eval/commission_examples/examples.jsonl`

| Area | high | not_high (outside) | not_high (Art. 6(3) filter) | Total |
| --- | ---: | ---: | ---: | ---: |
| Annex I: safety components | 8 | 4 | – | 12 |
| III.1 Biometrics | 14 | 26 | 0 | 40 |
| III.2 Critical infrastructure | 10 | 16 | 0 | 26 |
| III.3 Education | 12 | 9 | 10 | 31 |
| III.4 Employment | 14 | 11 | 7 | 32 |
| III.5 Essential services | 22 | 20 | 6 | 48 |
| III.6 Law enforcement | 15 | 28 | 4 | 47 |
| III.7 Migration and borders | 20 | 13 | 11 | 44 |
| III.8 Justice and democracy | 7 | 14 | 6 | 27 |
| **Total** | **122** | **141** | **44** | **307** |

Every area × verdict cell holds at least 4 examples, so B3's stratified split can put every stratum in both piles.

47 rows carry `review_flags` (examples to check by hand, listed in the report to the user). If all 47 were
dropped, 260 examples would remain (109 high, 151 not_high). That is still far above the threshold.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Split (Pile A / Pile B) | Example count against INIT's "about 40" threshold | 307 examples (260 without any flagged row); every area × verdict stratum has ≥ 4 | `eval/commission_examples/examples.jsonl`, command above |
| Leave-one-out | Same count | Only needed below about 40 examples | INIT > Benchmark isolation 2 |

## Decision
**Split.** The draft holds 307 counted examples, far above INIT's threshold of about 40, and still 260 if every
flagged row is set aside. The rule that decided it is INIT's "split if about 40 or more, leave-one-out otherwise".

## Consequences
- B3 writes `eval/split.json` with `mode: split`, stratified by `area` × `verdict` (18 strata), and commits it
  before any file under `backend/aiact/engine/` exists.
- C2 has to tag guideline chunks with `hr-ex-NNN` using the rule under "What counts as an example", reading only
  the `pile_b` IDs from `eval/split.json`. Any example C2 cannot map to an ID is an isolation gap, which B13 has to
  catch.
- B4 rewrites every Pile B example as a company description, and the user approves every label. A half split
  puts about 150 examples in Pile B. That is a large authoring and approval load, and choosing a smaller Pile B is
  a separate question for B3/B4.
- If the user's check changes the counted set (adds, drops or merges rows), IDs are renumbered and this record is
  updated before B3 runs. After `eval/split.json` is committed, the IDs are frozen.
- Revisit if the Commission adopts final high-risk guidelines (checked by W0). The examples and their numbering
  may change, and this extraction then covers the draft only.
