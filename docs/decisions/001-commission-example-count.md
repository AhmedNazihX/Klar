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
give each example the same `source_example_id` from the PDF alone, without reading `eval/`. The anchor table
further down names every counted list with its first and last ID, so the rule can be checked list by list.

1. **Sources.** Exactly these, and nothing else:
   - `guide-high-risk-general`: this part has no examples.
   - `guide-high-risk-annex-i`: the named systems in paras. (43), (45), (46), (47) and (49), 12 in total
     (anchor rows 1–5). Para. (43) holds two systems: the gas-appliance optimiser, then the heating-schedule
     optimiser ("Conversely, …"). Para. (49) is one example, the smart thermostat.
   - `guide-high-risk-annex-iii`:
     - every list under a heading that contains "Practical example", singular or plural, matched
       case-insensitively. There are 72 of these. The printed headings vary: most read "a)/b)/c) Practical
       examples of AI systems falling within / outside …", but variants include "Practical example**s for** AI
       systems" (4(b) c), 6(b) a) and b)), "Practical example **of an AI system**" (for example critical digital
       infrastructure a), gas a), 7(a) a)), a heading without "falling" (heating a)), and "falling within **the
       scope of** point 6(b)". Three headings print the letter on a line of its own (5(c) a), 5(d) a) and c));
       it is still part of the heading.
     - exactly two further lists that have no such heading, named here explicitly:
       - the cybersecurity list in section 3.2.1, introduced by "Examples of AI systems used solely for
         cybersecurity purposes, thus falling outside the use case of point 2 of Annex III AI Act:" (PDF page 41,
         hr-ex-053…056);
       - the list in para. (372) of section 3.6.7, introduced by "Below are some examples of AI systems used by law
         enforcement authorities that would not generally be classified as high-risk pursuant to Article 6(2) AI
         Act and point 6 of Annex III" (PDF pages 116–117, hr-ex-228…236).
     No other list outside a "Practical example" heading is counted, even if it states a verdict (see 5).
2. **Unit: one bullet = one example.**
   - Each top-level bullet ("–" or "-") is one example, even when it names several systems (for example
     hr-ex-028, 058, 228, 290, 299).
   - A bullet with "o" sub-bullets counts once per sub-bullet, and its opening sentence is stored as `lead_in`.
     This happens twice in point 1(a) b): five verification systems (hr-ex-021…025) and four presence-detection
     systems (hr-ex-034…037).
   - Three verdict headings have no bullet markers. Gas (p. 46, hr-ex-068) and heating (p. 47, hr-ex-069) have one
     paragraph each, so one example each. The electricity heading on p. 48 ("a) Practical examples of an AI system
     falling within the high-risk use case of the supply of electricity") has two unbulleted paragraphs, starting
     "An AI system used in a surveillance and protection …" (hr-ex-070) and "An AI system used for the detection
     of anomalies …" (hr-ex-071).
3. **Order and IDs.** Annex I examples come first, then Annex III, each in document order. IDs run from
   `hr-ex-001` to `hr-ex-307`.
4. **Verdict.**
   - Annex III: a "within" heading gives `high`. An "outside" or "exempted by the filter" heading gives `not_high`,
     and `basis` records which of the two (`outside_use_case` or `art_6_3_filter`).
   - The cybersecurity list and the para. (372) list give `not_high` with basis `outside_use_case`, status
     `settled`. hr-ex-230 (number-plate readers) carries a softer-verdict note, because the text warns about later
     surveillance risk.
   - Annex I: a safety component (paras. 43, 45, 46) gives `high` with basis `safety_component`. Paras. 43, 47 and
     49 give `not_high` with basis `not_safety_component`.
5. **Not counted.** Illustrations inside the running text are not counted, even where the introducing sentence
   states a verdict. They stay in the corpus in both modes. A final scan of all three PDFs for lists outside a
   "Practical example" heading found these (PDF pages; user decision 2026-09-28 for pp. 17–22):
   - Annex III, definitional illustrations of biometric data, biometric identification and RBI:
     - pp. 17–18: "For example, the following AI systems do not fall within the use case of point 1 of Annex III:"
       (3 bullets);
     - p. 18: "Examples with regard to the element of biometric data:";
     - p. 20: "For example, the following AI systems are not considered biometric identification systems:"
       (4 bullets);
     - p. 21: "For example, the following AI systems are considered biometric identification systems:";
     - pp. 21–22: "For example:" (after para. (136), on biometric verification versus RBI);
     - p. 22: "For example, the following would not be considered an RBI system";
     - p. 23: "For example, the following biometric identification can be considered remote:".
   - Annex III, RBI search examples: p. 29 "Example of targeted searches:" and "Examples of initial
     identification:"; p. 30 "Examples of initial identification include:"; p. 32 "Examples of AI systems that are
     not considered RBIs:"; p. 33 "Examples of untargeted searches include:".
   - Annex III, other running-text examples: the "Example:" boxes and "For example" passages in section 2 (pp.
     7–15); the IRB example (p. 94); the customs example (p. 103).
   - Annex I: the "Safety functions – indicative examples" list on pp. 6–7, including "By way of example, the
     following functions are not in themselves safety functions:" (p. 7); and the generic smart-appliance
     statement in para. (48) (p. 10).
   The scan also found lists that state no verdict about a system, and these are not examples: the list of areas
   (p. 5), the reference databases (p. 24), the Art. 26(10) authorisation cases (p. 31), the CER "This includes:"
   lists (pp. 42–47), the quoted wording of Annex III point 4 (p. 61), the law-enforcement authorities (p. 101),
   the evidence-evaluation task types in 6(c) (p. 109), the border authorities (p. 118), the ADR entities
   (p. 141) and the deployer types in 8(b) (p. 144).
6. **Pages.** `page` is the physical PDF page on which the example starts. `printed_page` is the number printed on
   it, which is one lower in all three PDFs because the cover page carries no number.
7. **Text.** `text` and `lead_in` are verbatim, with line-break hyphenation joined. Inline footnote reference
   numbers are left out (for example, "chatbot114" in the PDF is "chatbot" in hr-ex-306), and footnotes are not
   included.
8. **Headings.** `list_heading` is the printed heading, including its letter. For the two non-heading lists it holds
   the introducing sentence. Annex I lists have no heading, so `list_heading` holds the paragraph number
   ("para. (45)"), and the anchor table gives the introducing words.

## Anchor table
One row per counted list. "PDF pages" are the pages on which the list's examples start. The rows sum to 307, and
each row's first and last ID and row count were checked against `examples.jsonl`.

| # | Part | PDF pages | Heading or introducing text (as printed) | First ID | Last ID | Rows |
| --- | --- | --- | --- | --- | --- | ---: |
| 1 | I | 8 | para. (43): "By way of illustration, an AI system designed to optimise combustion efficiency …", then "Conversely, an AI system that merely optimises heating schedules …" | hr-ex-001 | hr-ex-002 | 2 |
| 2 | I | 9 | para. (45): "AI systems that are intended to fulfil a safety function and are therefore considered a safety component … include, inter alia:" | hr-ex-003 | hr-ex-006 | 4 |
| 3 | I | 9 | para. (46): "… Examples of AI systems that may be classified as safety components based on safety risks related to failure or malfunctioning include:" | hr-ex-007 | hr-ex-009 | 3 |
| 4 | I | 10 | para. (47): "… An example of such systems includes:" | hr-ex-010 | hr-ex-011 | 2 |
| 5 | I | 10 | para. (49): "By way of example, a smart thermostat covered by the Radio Equipment Directive …" | hr-ex-012 | hr-ex-012 | 1 |
| 6 | III | 24–25 | a) Practical examples of AI systems falling within the high-risk use case of point 1(a) | hr-ex-013 | hr-ex-019 | 7 |
| 7 | III | 25–28 | b) Practical examples of AI systems falling outside the high-risk use case of point 1(a) | hr-ex-020 | hr-ex-039 | 20 |
| 8 | III | 36 | a) Practical examples of AI systems falling within the high-risk use case of point 1(b) | hr-ex-040 | hr-ex-041 | 2 |
| 9 | III | 36 | b) Practical examples of AI systems falling outside the high-risk use case of point 1(b) | hr-ex-042 | hr-ex-045 | 4 |
| 10 | III | 38 | a) Practical examples of AI systems falling within the high-risk use case of point 1(c) | hr-ex-046 | hr-ex-050 | 5 |
| 11 | III | 39 | b) Practical examples of AI systems falling outside the high-risk use case of point 1(c) | hr-ex-051 | hr-ex-052 | 2 |
| 12 | III | 41 | Examples of AI systems used solely for cybersecurity purposes, thus falling outside the use case of point 2 of Annex III AI Act: | hr-ex-053 | hr-ex-056 | 4 |
| 13 | III | 43 | a) Practical example of an AI system falling within the high-risk use case of critical digital infrastructure | hr-ex-057 | hr-ex-057 | 1 |
| 14 | III | 43 | b) Practical examples of AI systems falling outside the high-risk use case of critical digital infrastructure | hr-ex-058 | hr-ex-058 | 1 |
| 15 | III | 44 | a) Practical examples of AI systems falling within the high-risk use case of road traffic | hr-ex-059 | hr-ex-063 | 5 |
| 16 | III | 45 | b) Practical examples of AI systems falling outside the high-risk use case of the road traffic | hr-ex-064 | hr-ex-065 | 2 |
| 17 | III | 45–46 | a) Practical examples of AI systems falling within the high-risk use case of water supply | hr-ex-066 | hr-ex-067 | 2 |
| 18 | III | 46 | a) Practical example of an AI system falling outside of the high-risk use case of the supply of gas | hr-ex-068 | hr-ex-068 | 1 |
| 19 | III | 47 | a) Practical examples of AI systems outside the high-risk use case of the supply of heating | hr-ex-069 | hr-ex-069 | 1 |
| 20 | III | 48 | a) Practical examples of an AI system falling within the high-risk use case of the supply of electricity | hr-ex-070 | hr-ex-071 | 2 |
| 21 | III | 48–49 | b) Practical examples of AI systems falling outside the high-risk use case of the supply of electricity | hr-ex-072 | hr-ex-078 | 7 |
| 22 | III | 52 | a) Practical examples of AI systems falling within the high-risk use case of point 3(a) | hr-ex-079 | hr-ex-082 | 4 |
| 23 | III | 53 | b) Practical examples of AI systems falling outside the high-risk use case of point 3(a) | hr-ex-083 | hr-ex-084 | 2 |
| 24 | III | 53 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) | hr-ex-085 | hr-ex-087 | 3 |
| 25 | III | 55 | a) Practical examples of AI systems falling within the high-risk use case of point 3(b) | hr-ex-088 | hr-ex-089 | 2 |
| 26 | III | 55 | b) Practical examples of AI systems falling outside the high-risk use case of point 3(b) | hr-ex-090 | hr-ex-092 | 3 |
| 27 | III | 56 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) | hr-ex-093 | hr-ex-095 | 3 |
| 28 | III | 57–58 | a) Practical examples of AI systems falling within the high-risk use case of point 3(c) | hr-ex-096 | hr-ex-098 | 3 |
| 29 | III | 58 | b) Practical examples of AI systems falling outside the high-risk use case of point 3(c) | hr-ex-099 | hr-ex-100 | 2 |
| 30 | III | 58 | c) Practical examples of AI systems falling within the use cases but exempted by the filter mechanism of Article 6(3) | hr-ex-101 | hr-ex-102 | 2 |
| 31 | III | 59–60 | a) Practical examples of AI systems falling within the high-risk use case of point 3(d) | hr-ex-103 | hr-ex-105 | 3 |
| 32 | III | 60 | b) Practical examples of AI systems falling outside the high-risk use case of point 3(d) | hr-ex-106 | hr-ex-107 | 2 |
| 33 | III | 60 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) | hr-ex-108 | hr-ex-109 | 2 |
| 34 | III | 67–69 | a) Practical examples of AI systems falling within the high-risk use case of point 4(a) | hr-ex-110 | hr-ex-118 | 9 |
| 35 | III | 69–70 | b) Practical examples of AI system falling outside the high-risk use case of point 4(a) | hr-ex-119 | hr-ex-124 | 6 |
| 36 | III | 70–71 | c) Practical examples of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-125 | hr-ex-129 | 5 |
| 37 | III | 77–78 | a) Practical examples of AI systems falling within the high-risk use case of point 4(b) | hr-ex-130 | hr-ex-134 | 5 |
| 38 | III | 78–79 | b) Practical examples of AI systems falling outside the high-risk use case of point 4(b) | hr-ex-135 | hr-ex-139 | 5 |
| 39 | III | 79 | c) Practical examples for AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-140 | hr-ex-141 | 2 |
| 40 | III | 83–84 | a) Practical examples of AI systems falling within the high-risk use case of point 5(a) | hr-ex-142 | hr-ex-151 | 10 |
| 41 | III | 84–85 | b) Practical examples of AI systems falling outside the high-risk use case of point 5(a) | hr-ex-152 | hr-ex-155 | 4 |
| 42 | III | 85–86 | c) Practical examples of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-156 | hr-ex-159 | 4 |
| 43 | III | 89 | a) Practical examples of AI systems falling within the high-risk use case of point 5(b) | hr-ex-160 | hr-ex-161 | 2 |
| 44 | III | 89–90 | b) Practical examples of AI systems falling outside the high-risk use case of point 5(b) | hr-ex-162 | hr-ex-168 | 7 |
| 45 | III | 92–93 | a) Practical examples of AI systems falling within the high-risk use case of point 5(c) | hr-ex-169 | hr-ex-170 | 2 |
| 46 | III | 93 | b) Practical examples of AI systems falling outside the high-risk use case of point 5(c) | hr-ex-171 | hr-ex-172 | 2 |
| 47 | III | 97–98 | a) Practical examples of AI systems falling within the high-risk use case of point 5(d) | hr-ex-173 | hr-ex-180 | 8 |
| 48 | III | 98–99 | b) Practical examples of AI systems falling outside the high-risk use case of point 5(d) | hr-ex-181 | hr-ex-187 | 7 |
| 49 | III | 99–100 | c) Practical examples of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-188 | hr-ex-189 | 2 |
| 50 | III | 106 | a) Practical examples of AI systems falling within the use case of point 6(a) | hr-ex-190 | hr-ex-192 | 3 |
| 51 | III | 107 | b) Practical examples of AI systems falling outside the use case of point 6(a) | hr-ex-193 | hr-ex-197 | 5 |
| 52 | III | 108 | a) Practical examples for AI systems falling within the scope of point 6(b) | hr-ex-198 | hr-ex-198 | 1 |
| 53 | III | 108–109 | b) Practical examples for AI systems falling outside of the use case point 6(b) | hr-ex-199 | hr-ex-201 | 3 |
| 54 | III | 109–110 | a) Practical examples of AI systems falling within the use case of point 6(c) | hr-ex-202 | hr-ex-205 | 4 |
| 55 | III | 111 | b) Practical examples of AI systems falling outside the use case of point 6(c) | hr-ex-206 | hr-ex-212 | 7 |
| 56 | III | 112 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) AI Act | hr-ex-213 | hr-ex-214 | 2 |
| 57 | III | 113 | a) Practical examples of AI systems falling within the use case of point 6(d) | hr-ex-215 | hr-ex-218 | 4 |
| 58 | III | 114 | b) Practical examples of AI systems falling outside the use case of point 6(d) | hr-ex-219 | hr-ex-219 | 1 |
| 59 | III | 114 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) AI Act | hr-ex-220 | hr-ex-221 | 2 |
| 60 | III | 115 | a) Practical examples of AI systems falling within the use case of point 6(e) | hr-ex-222 | hr-ex-224 | 3 |
| 61 | III | 115–116 | b) Practical examples of AI systems falling outside the use case of point 6(e) | hr-ex-225 | hr-ex-227 | 3 |
| 62 | III | 116–117 | (372) Below are some examples of AI systems used by law enforcement authorities that would not generally be classified as high-risk pursuant to Article 6(2) AI Act and point 6 of Annex III … | hr-ex-228 | hr-ex-236 | 9 |
| 63 | III | 122 | a) Practical example of an AI system falling within the use case of point 7(a) of Annex III | hr-ex-237 | hr-ex-238 | 2 |
| 64 | III | 123 | b) Practical examples of AI systems falling outside of the use case of point 7(a) of Annex III | hr-ex-239 | hr-ex-240 | 2 |
| 65 | III | 123 | c) Practical examples of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-241 | hr-ex-241 | 1 |
| 66 | III | 124–125 | a) Practical examples of AI systems falling within the use case of point 7(b) of Annex III | hr-ex-242 | hr-ex-249 | 8 |
| 67 | III | 126 | b) Practical examples of AI systems falling outside the use case of point 7(b) of Annex III | hr-ex-250 | hr-ex-254 | 5 |
| 68 | III | 128 | a) Practical examples of AI systems falling within the use case of point 7(c) of Annex III | hr-ex-255 | hr-ex-259 | 5 |
| 69 | III | 128 | b) Practical examples of an AI system falling outside the use case of point 7(c) of Annex III | hr-ex-260 | hr-ex-260 | 1 |
| 70 | III | 129–130 | c) Practical examples of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-261 | hr-ex-269 | 9 |
| 71 | III | 130–131 | a) Practical examples of AI systems falling within the use case of point 7(d) of Annex III | hr-ex-270 | hr-ex-274 | 5 |
| 72 | III | 131–132 | b) Practical examples of AI systems falling outside the use case of point 7(d) of Annex III | hr-ex-275 | hr-ex-279 | 5 |
| 73 | III | 132 | c) Practical example of AI systems falling within the use case but exempted under the filter mechanism of Article 6(3) | hr-ex-280 | hr-ex-280 | 1 |
| 74 | III | 136–137 | a) Practical examples of AI systems falling within the use case of point 8(a) | hr-ex-281 | hr-ex-284 | 4 |
| 75 | III | 137–139 | b) Practical examples of AI systems falling outside the use case of point 8(a) | hr-ex-285 | hr-ex-290 | 6 |
| 76 | III | 139–140 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) AI Act | hr-ex-291 | hr-ex-295 | 5 |
| 77 | III | 146 | a) Practical examples of AI systems falling within the use case of point 8(b) of Annex III | hr-ex-296 | hr-ex-298 | 3 |
| 78 | III | 146–147 | b) Practical examples of AI systems falling outside of the use case of point 8(b) | hr-ex-299 | hr-ex-306 | 8 |
| 79 | III | 147 | c) Practical examples of AI systems falling within the use case but exempted by the filter mechanism in Article 6(3) AI Act | hr-ex-307 | hr-ex-307 | 1 |
| | | | **Total** (5 Annex I lists + 72 "Practical example" lists + 2 named lists) | | | **307** |

## Label fields
Every row of `eval/commission_examples/examples.jsonl` carries the same fields. The verbatim fields (`text`,
`lead_in`, `list_heading`, `subheading`) come from the PDF, subject to rules 7 and 8.

| Field | Meaning | Default | Rows that differ |
| --- | --- | --- | --- |
| `accepted_bases` | Every basis that counts as correct. An Art. 6(3) entry can name the letter, e.g. `art_6_3_filter:d` | `[basis]` | 3 with two entries: hr-ex-241 (6(3)(d) or outside 7(a)), 291 (6(3)(a) or (d)), 294 (6(3)(b) or outside 8(a)) |
| `label_status` | `settled` or `legally_ambiguous` | `settled` | 1: hr-ex-307 |
| `flip_variants` | A list of `{feature, resulting_verdict, provision}`: a "however / if" feature in the guidelines that would change the verdict | `[]` | 15 (see the product rule below) |
| `notes` | Label notes | `[]` | 10: the Art. 6(1) note on the 8 Annex I high rows, the softer-verdict note on hr-ex-230, both readings on hr-ex-307 |
| `review_resolution` | How the user resolved a row flagged for review | `null` | 47 |

**Matching `accepted_bases`.**
- Every row's `accepted_bases` contains its `basis`, either bare or in a lettered form (`art_6_3_filter:<x>`).
  This was checked on all 307 rows.
- A bare `art_6_3_filter` answer matches any lettered `art_6_3_filter:<x>` entry.
- A lettered answer `art_6_3_filter:<x>` matches an entry with the same letter, or a bare `art_6_3_filter` entry.
- Any other basis must match exactly.

**`flip_variants.resulting_verdict`** takes one of three values: `high`, `not_high` or `prohibited`. `prohibited`
occurs only in flip variants (hr-ex-244, 245). It is not a value of `verdict`.

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
Recount by area and verdict:
`jq -rs 'group_by(.area)[] | [.[0].area, (map(select(.verdict=="high"))|length), (map(select(.verdict=="not_high"))|length), length] | @tsv' eval/commission_examples/examples.jsonl`

Recount of the not_high split (outside or not a safety component, versus the Art. 6(3) filter):
`jq -rs 'group_by(.area)[] | [.[0].area, (map(select(.basis=="outside_use_case" or .basis=="not_safety_component"))|length), (map(select(.basis=="art_6_3_filter"))|length)] | @tsv' eval/commission_examples/examples.jsonl`

| Area | high | not_high: outside use case (Annex I: not a safety component) | not_high: Art. 6(3) filter | Total |
| --- | ---: | ---: | ---: | ---: |
| Annex I: safety components | 8 | 4 (`not_safety_component`) | – | 12 |
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
The counts were recounted after every review edit and are unchanged.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Split (Pile A / Pile B) | Example count against INIT's "about 40" threshold | 307 examples; every area × verdict stratum has ≥ 4 | `eval/commission_examples/examples.jsonl`, commands above |
| Leave-one-out | Same count | Only needed below about 40 examples | INIT > Benchmark isolation 2 |

## Decision
**Split.** The draft holds 307 counted examples, far above INIT's threshold of about 40 (before the review, even
setting aside all 47 flagged rows left 260). The rule that decided it is INIT's "split if about 40 or more,
leave-one-out otherwise".

## User review (2026-09-28, relayed by the orchestrator)
No rows were added, dropped, merged or split, so the count stays at 307 and the IDs are unchanged.

1. Annex I (hr-ex-001…012): verdicts kept (8 high, 4 not_high). The Art. 6(1) note goes on each high row.
2. Both lists outside a "Practical examples" heading are counted (hr-ex-053…056, 228…236), and they are named
   explicitly in rule 1. hr-ex-230 (number-plate readers) is noted as a softer verdict.
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
8. hr-ex-070 and 071 stay two `high` examples (rule 2).
9. The scope rule is confirmed: running-text illustrations are not counted and stay in the corpus. The lists on
   Annex III pp. 17–22 are not counted either (decision of the second review, 2026-09-28).
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
- **C2:** tag guideline chunks with `hr-ex-NNN` using rules 1–3 and the anchor table: the "Practical example"
  heading test, exactly the two named extra lists, one bullet = one example, and the two electricity paragraphs.
  C2 reads only the `pile_b` IDs. It can check its derivation against the anchor table's first/last IDs and row
  counts, which are in `docs/`, not `eval/`. Any example C2 cannot map to an ID is an isolation gap, which B13
  has to catch.
- **E2 (facts) and the product rule:** when a described system matches a base example that has a flip variant,
  the engine asks a key-fact follow-up question about the variant feature, or flags it.
- **V2 (metrics):** score a result's basis as correct under the `accepted_bases` matching rule above. Report
  `legally_ambiguous` rows under uncertain-outcome handling, not plain accuracy.
- **F7 (`BenchmarkCase`):** support any-of citation or basis matching (a list of accepted values, with the bare
  versus lettered Art. 6(3) rule above), plus a `label_status` field.
- Revisit if the Commission adopts final high-risk guidelines (checked by W0). The examples and their numbering
  may change, and this extraction then covers the draft only.
