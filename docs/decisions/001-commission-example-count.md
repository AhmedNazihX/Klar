# 001 · Commission high-risk examples: count and split mode

- **Date:** 2026-09-28
- **Story:** B2 (docs/BACKLOG.md)
- **Status:** accepted (the user reviewed the extraction and approved it on 2026-09-28, relayed by the orchestrator)

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
   - `guide-high-risk-annex-iii`: every list under a heading that states a verdict. In practice that is:
     - every list under a heading that begins "Practical example(s) of AI systems falling within / outside /
       within the use case but exempted …" (72 lists);
     - every explicit verdict list outside such a heading, where the introducing sentence itself says the listed
       systems fall outside (or within) a use case. The draft has two: the cybersecurity list in section 3.2.1,
       which begins "Examples of AI systems used solely for cybersecurity purposes, thus falling outside the use
       case of point 2" (PDF page 41), and the list in para. (372) of section 3.6.7, "would not generally be
       classified as high-risk" (PDF pages 116–117).
2. **Unit: one bullet = one example.**
   - Each top-level bullet ("–" or "-") is one example, even when it names several systems (for example
     hr-ex-028, 058, 228, 290, 299).
   - A bullet with "o" sub-bullets counts once per sub-bullet, and its opening sentence is stored as `lead_in`.
     This happens twice in point 1(a): five verification systems and four presence-detection systems.
   - Where a verdict heading has no bullet markers, each paragraph that starts a new system counts as one example.
     This covers gas (1), heating (1) and electricity "within" (2).
3. **Order and IDs.** Annex I examples come first, then Annex III, each in document order. IDs run from
   `hr-ex-001` to `hr-ex-307`.
4. **Verdict.**
   - Annex III: a "within" heading gives `high`. An "outside" or "exempted by the filter" heading gives `not_high`,
     and `basis` records which of the two (`outside_use_case` or `art_6_3_filter`).
   - Annex I: a safety component (paras. 43, 45, 46) gives `high`, and paras. 43, 47 and 49 give `not_high`.
5. **Not counted.** Illustrations inside the running text are not counted, because they sit under no verdict
   heading. They stay in the corpus in both modes. Where they are:
   - Annex III: the "Example:" boxes and "For example" passages in section 2 (PDF pages 7–15); the RBI search
     examples (pages 29–33); the IRB example (page 94); the customs example (page 103).
   - Annex I: the "Safety functions – indicative examples" list (PDF pages 6–7) and the generic smart-appliance
     statement in para. (48).
6. **Pages.** `page` is the physical PDF page. `printed_page` is the number printed on it, which is one lower in
   all three PDFs because the cover page carries no number.

## Label fields
Every row of `eval/commission_examples/examples.jsonl` carries the same fields. The verbatim fields (`text`,
`lead_in`, `list_heading`, `subheading`) are copied from the PDF and never edited.

| Field | Meaning | Default | Rows that differ |
| --- | --- | --- | --- |
| `accepted_bases` | Every basis that counts as correct. An Art. 6(3) entry can name the letter, e.g. `art_6_3_filter:d` | `[basis]` | 3 with two entries: hr-ex-241 (6(3)(d) or outside 7(a)), 291 (6(3)(a) or (d)), 294 (6(3)(b) or outside 8(a)) |
| `label_status` | `settled` or `legally_ambiguous` | `settled` | 1: hr-ex-307 |
| `flip_variants` | A list of `{feature, resulting_verdict, provision}`: a "however / if" feature in the guidelines that would change the verdict | `[]` | 15 (see the product rule below) |
| `notes` | Label notes | `[]` | 10: the Art. 6(1) note on the 8 Annex I high rows, the softer-verdict note on hr-ex-230, both readings on hr-ex-307 |
| `review_resolution` | How the user resolved a row flagged for review | `null` | 47 |

**Annex I note** (on hr-ex-001 and 003–009): "Art. 6(1): a safety component is high-risk only if its product also
needs a third-party conformity assessment under the sectoral law; the guidelines don't state this, so the label
assumes it."

**hr-ex-307** is `legally_ambiguous`. Its verdict stays `not_high` as the Commission's leaning ("could be exempted",
Art. 6(3)(b)). The other reading, in `notes`, is that the system falls within Annex III 8(b) and the exemption does
not hold.

## Product rule: verdict-flipping features
Sometimes the guidelines give a "however / if" feature that would flip a verdict. In that case the assistant must
ask a key-fact follow-up question about that feature, or flag it, because a user may describe the base version
while the real system has the variant feature. The 15 rows with a non-empty `flip_variants` record these features:

- Not high-risk here, but high-risk under another point if the feature is present: hr-ex-029 (7(c) or 1(b)),
  042 (7(b)), 107 (1(a)), 122 (4(b)), 193 (6(d)), 194 (1), 210 (6(a)).
- Hedged verdicts:
  - hr-ex-226: enrichment with personal data, building individual profiles, gives 6(e) high.
  - hr-ex-241: any truthfulness or deception inference gives 7(a) high, with no exemption.
  - hr-ex-283: a downward variant. Step (i) alone falls under Art. 6(3)(d), so it is not high-risk.
  - hr-ex-291: admissibility recommendations beyond technical checks give 8(a) high, with no exemption.
  - hr-ex-294: changing the content of the decision may give 8(a) high.
  - hr-ex-307: generating new content or targeting voters gives 8(b) high, with no exemption.
- Prohibition variants: hr-ex-244 (Art. 5(1)(c)) and 245 (Art. 5(1)(c) and 5(1)(d)).

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
The counts were recounted after the review edits and are unchanged.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Split (Pile A / Pile B) | Example count against INIT's "about 40" threshold | 307 examples; every area × verdict stratum has ≥ 4 | `eval/commission_examples/examples.jsonl`, command above |
| Leave-one-out | Same count | Only needed below about 40 examples | INIT > Benchmark isolation 2 |

## Decision
**Split.** The draft holds 307 counted examples, far above INIT's threshold of about 40 (before the review, even
setting aside all 47 flagged rows left 260). The rule that decided it is INIT's "split if about 40 or more,
leave-one-out otherwise".

## User review (2026-09-28, relayed by the orchestrator)
No rows were added, dropped, merged or split, so the count stays at 307 and the IDs are unchanged.

1. Annex I (hr-ex-001…012): verdicts kept (8 high, 4 not_high). The Art. 6(1) note goes on each high row.
2. Both lists outside a "Practical examples" heading are counted (hr-ex-053…056, 228…236). The counting rule was
   widened to match. hr-ex-230 (number-plate readers) is noted as a softer verdict because of its caveat about
   later surveillance risk.
3. Multi-system bullets (hr-ex-028, 058, 228, 290, 299): one row per bullet.
4. hr-ex-029, 042, 107, 122, 193, 194 and 210 stay `not_high`. Each row records the other point and the feature
   that would flip the verdict.
5. Hedged verdicts:
   - hr-ex-226: stays `not_high`.
   - hr-ex-241: stays `not_high`, and either basis is accepted.
   - hr-ex-283: stays `high`.
   - hr-ex-291: stays `not_high`, accepting 6(3)(a) or (d).
   - hr-ex-294: stays `not_high`, and either basis is accepted.
   - hr-ex-307: `legally_ambiguous`, with the verdict kept as `not_high`.
   The variants are recorded in `flip_variants`.
6. hr-ex-244 and 245 stay `high`. The Art. 5 prohibition variants are recorded.
7. hr-ex-037 stays its own example (`not_high`).
8. hr-ex-070 and 071 stay two `high` examples. The rule for unmarked lists is stated above.
9. The scope rule is confirmed: running-text illustrations are not counted and stay in the corpus.
10. The user spot-checked hr-ex-003 (Annex I p. 9), 047 (p. 38), 118 (p. 69), 176 (p. 97) and 262 (p. 129). All
    match on page, heading and one-bullet split.

## Consequences
- B3 writes `eval/split.json` with `mode: split`, stratified by `area` × `verdict` (18 strata), and commits it
  before any file under `backend/aiact/engine/` exists. After that commit the IDs are frozen.
- **Open question for B3/B4: Pile B size.** A half split puts about 150 examples in Pile B, and B4 rewrites every
  one with a user-approved label. That is a large authoring and approval load. Whether to use a smaller Pile B is
  still to be decided.
- **B4:** carry `accepted_bases`, `label_status` and `flip_variants` into the cases. A Pile B row with a flip
  variant can also produce a variant case labelled with the variant's verdict. hr-ex-307 becomes a
  `legally_ambiguous` case.
- **B6 (soft-wording pairs):** the flip-variant rows are natural sources for base-versus-variant pairs.
- **C2:** tag guideline chunks with `hr-ex-NNN` using the counting rule above, including the two verdict lists
  outside a "Practical examples" heading and the one-paragraph-per-system rule. C2 reads only the `pile_b` IDs.
  Any example C2 cannot map to an ID is an isolation gap, which B13 has to catch.
- **E2 (facts) and the product rule:** when a described system matches a base example that has a flip variant,
  the engine asks a key-fact follow-up question about the variant feature, or flags it.
- **V2 (metrics):** score a result as correct when its basis matches any entry in `accepted_bases`. Report
  `legally_ambiguous` rows under uncertain-outcome handling, not plain accuracy.
- **F7 (`BenchmarkCase`):** support any-of citation or basis matching (a list of accepted citations), plus a
  `label_status` field.
- Revisit if the Commission adopts final high-risk guidelines (checked by W0). The examples and their numbering
  may change, and this extraction then covers the draft only.
