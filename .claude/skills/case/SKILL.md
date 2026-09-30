---
name: case
description: Guides writing labelled benchmark cases for the AI Act project (eval/cases/**) — own cases per category, rewritten Commission Pile B examples, soft-wording pairs, consistency triples, Q&A items and Annex-matching items — with the cite-or-ambiguous label rule, the rewrite rules, a similarity check and user approval. Use for stories B4–B8, B12 and X0, or whenever the user asks to write, draft, add, fix or review a test case or label.
argument-hint: "<set or category> [count]"
---

# Write benchmark cases: $ARGUMENTS

Benchmark labels are the answer key the project's published accuracy rests on. **The agent drafts;
the user decides.** No case counts as done until the user has approved its label.

## 0. Before writing

- Read INIT › Evaluation (Test sets, Label rules, Benchmark isolation) and INIT › How it works (Risk classes, Outcomes, Roles).
  INIT is `AI Act Classification Assistant — Capstone Init Document.md`.
- **Schema:** `backend/aiact/eval/cases.py` (story F7) is the source of truth. If it doesn't exist yet,
  stop: F7 must be merged first. Validate every file you write with the loader.
- **Frozen labels:** if tag `labels-v1` exists (`git tag -l labels-v1`), every change to an existing case
  needs an entry in `eval/LABEL_CHANGES.md` (date, case_id, old label → new label, reason, reviewed by the user).
- **Isolation:** cases live only under `eval/`. Never write to `data/`, the corpus tables or seed files.
  Never copy case text into code comments, prompts or fixtures outside `eval/`.

## 1. The label rules (INIT › Label rules)

- **Cite or ambiguous.** Every label names the provision or Commission example that settles it, in `label_citation`,
  for example `art:6:3`, `annex:III:4:a` or `guide:hr:ex:17`. If nothing settles it, the correct label is status
  `legally_ambiguous`, with the open question and both readings in `notes`. Never guess a class to avoid ambiguity.
- **Label the working assumption.** For an ambiguous case, `risk_class` holds the stricter reading (INIT › Risk classes).
- **The law as amended.** Label against the Act as amended by the Omnibus (2026/1744), as of the case's
  date. Watch the dates:
  - the December 2026 prohibitions apply from 2 Dec 2026;
  - the Art. 50(2) grace period applies until 2 Dec 2026, only for systems placed on the market before 2 Aug 2026;
  - Annex III obligations apply from 2 Dec 2027, Annex I from 2 Aug 2028.
- **Role is labelled too:** provider, deployer, importer or distributor, including Art. 25 switches.

## 2. How to write a description

Write the way a company describes its own tool, not the way the law does:
- Company size and sector, whether the tool was bought or built, what it's used for, who it affects.
- One or two irrelevant details, such as the vendor name, the rollout date or an unrelated feature.
- Plain business vocabulary. Don't use the Act's terms ("profiling", "biometric categorisation") unless a company would really say them.
- 60–150 words. At least 25% of each category in German, written natively, not translated word for word.

**Rewritten Commission examples (B4)** also follow INIT › Benchmark isolation 3:
- Never reuse the Commission's wording. No run of 8 or more words may be shared with the source example.
- Keep the facts that decide the verdict; change everything else (sector details, names, framing).
- Set `source_example_id` to the example's ID.
- Run the similarity check (below) on every case.

**Special sets:**
- **Soft-wording pairs (B6):** the same system twice, once plainly ("scores and ranks applicants") and once softened
  ("helps HR organise applications"). Both keep the same label and share a `pair_id` tag.
- **Consistency triples (B8):** three paraphrases of one system, with the same label. The facts may not differ.
- **Q&A (B7):** a question, the provision_ids a correct answer must cite, and a short reference answer.
- **Annex matching (X0):** an informal description mapped to the expected Annex point or points. Write these from scratch, never from Commission examples.

## 3. Similarity check (Pile B rewrites, and anything drawn from a source)

For each case, compare it with its source text: find the longest shared run of words (lowercased, punctuation removed).
For cases with a `source_example_id`, run `uv run aiact evaluate similarity` from `backend/` (B4a): it prints each case's
longest shared run with its source example's text and lead-in, and its cosine (after `aiact evaluate isolation-embed`).
For anything else drawn from a source, run a quick Python check in the scratchpad.
Report the maximum run per case, and rewrite any case at 8 words or more.

## 4. Approval loop

1. Draft a batch, at most 5–8 cases at a time, so the user can review them properly.
2. Show the user a table: case_id, a one-line gist, the label, the citation, the language, and any doubt you have about the label.
   Name the doubts plainly. A flagged doubt is worth more than a confident wrong label.
3. Write the files only after the user approves. Record the approval in the case's `notes`
   (`approved by user YYYY-MM-DD`).
4. Validate with the loader, and report the counts per category and language.
