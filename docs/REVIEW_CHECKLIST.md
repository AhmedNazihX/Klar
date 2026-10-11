# Pre-DONE review checklist

This list is grown from the critical, major and MEDIUM+ review findings, plus test-auditor gaps, that caused fix rounds between 2026-09-26 and 2026-10-07. Each item recurred in at least two stories.
Before reporting DONE, check your own diff against every item in your area and fix or explain each hit in your final report (its Checklist line).
Items marked *(isolation-auditor)* need folders the Engine and Corpus lanes can't read: workers in those lanes skip them, and the audit checks them.

## Engine (legal reading, citations, prompts)
- [ ] Run every new question, decision text, citation and hint under `law_version=original` as well as `amended`. Nothing Omnibus-only (Art. 6(1a)–(1c), 5(1)(ba)/(bb), 99(6a), small mid-caps, Art. 113(a)) may appear under the original text, and `?law=` values other than the two are dropped. (seen: P18, E4, E11, C7, P15, 6)
- [ ] Every date-dependent rule reads `as_of`, including the refusal path, the lookups and the benchmark runner. Have a test on each side of the date, and check each own case's launch and put-into-service dates against Art. 111/113. (seen: E4, B5c, F4, C3, C7b, P5, B5e, 13)
- [ ] An unknown, assumed or second-opinion answer never settles the lenient way. It keeps the stricter reading, asks its question once, and never shows duties or "if yes" outcomes as decided. (seen: F3, E7, C7b, E8, E12, 11)
- [ ] Put the guideline or Act paragraph next to every new prompt rule. Confirm the rule neither narrows nor widens that paragraph (modalities, carve-out conditions, examples). Confirm it contradicts neither another section of the same prompt nor another node's prompt. (seen: E6, E10, C7b, E2, 8)
- [ ] Every decided step cites the provision that decided it, including the definition behind a role switch. Confirm the cited provision really applies to that fact, and that every link the copy promises exists. (seen: E7, E2, P5, V2, 5)
- [ ] Write every prompt or `*_texts.py` line from the Act and the guidelines only, never from a benchmark example or a memory of one. The isolation-auditor runs decision 028's leak check on them (no shared 5-word run with Pile B outside the Act's wording, no paraphrase of a deciding feature); Engine workers can't, as it reads denied files. (seen: E2, E4, E12, 4)

## API & security
- [ ] The user's description and the model's reply never reach logs, traces, exception messages or `error` fields. Watch `raise … from exc` over a pydantic `ValidationError`, which carries `input_value`. Have a test that fails if they do. (seen: E10, E8, 3)
- [ ] Every input that reaches a paid call or a DB write has a size cap. The cap is enforced before the body is read or parsed, and is sized for the memory blow-up (JSON ×N), not just the byte count. (seen: P3b, P1, E10, 5)
- [ ] Every paid model call has three properties, each with a test:
  - it is pinned to its EU endpoint, with no silent fallback;
  - its retries are really bounded (check the SDK's meaning of `max_retries=0`);
  - it counts toward the cost cap even when it fails.
  (seen: V3, X3, X2, P1, V1, 6)
- [ ] `include_held_out` stays keyword-only and off by default, and it never becomes a field of a request model. A test drives a real node and shows the flag is neither dropped nor turned on. (seen: E10, C6, E9, 5)
- [ ] Grep new cassettes, recordings and any command output you add for key-shaped strings or values from `.env`. (seen: E3, T2, 2)

## Frontend
- [ ] Check every legal sentence in the locale JSON against the full consolidated article, including added paragraphs (6a, 1c, …), in both EN and DE. Don't write the copy from memory. (seen: P18, P5, 3)
- [ ] "Try again" sends the current form state. Nothing re-sends a paid request automatically, and an error state shows no class. A test counts the requests sent. (seen: P5, P1, 3)

## DB / corpus
- [ ] When a schema field becomes required or changes shape, add a test that a result stored before your story still loads. (seen: C9, E12, F3, 3)
- [ ] A provision ID points to the same text in EN and DE, and stays the same across reloads and draft-to-final changes. An upsert that changes the text invalidates its embedding. (seen: F4, C2, C1, C3, 7)
- [ ] Users can't write server-owned columns (timestamps, sizes, counts, slots) through RLS. The database sets them, and imports keep the original dates and order. (seen: P3, P3b, 3)

## Tests
- [ ] A missing recording must never let a replay skip silently or pass. Mark an xfail with its specific reason (`raises=` or a checker), not "any mismatch". The DoD replays must actually run. (seen: E5, E7, E8, E10, C7b, 7)
- [ ] Pin every cap, threshold, model slug and source literal with an assertion against a literal value. A cassette body mismatch or a comparison against the module's own constant doesn't count. (seen: E5, B4a, E6, V7, X2, 5)
- [ ] Every alternative the code handles separately gets its own test: each point ((ba) and (bb)), enum member, node, model arm and annex. Also test the production default path: the real connection, with no injected fake. (seen: E4, P5, X2, E10, E12, E5, E9, 14)
- [ ] Each test's fixture really differs on the property it asserts. Two `n/a` rows, one shared transaction or `now()`, or a check that can never fail on real data all prove nothing. (seen: C2, P3, B13, F7b, P8a, 5)
- [ ] Every new or changed user-visible string has its German twin asserted exactly, not only the English one. (seen: P18, E8, E11, 5)
- [ ] Tests don't depend on `.env` values or a heavy load on the shared database. Database tests use `TEST_DATABASE_URL` (default: the local Supabase), never the app's hosted `DATABASE_URL`; an unreachable test database skips them locally and fails them in CI. (seen: C8, E9, P3b, 3)

## Eval cases & harness
- [ ] A matcher checks exactly what the case's tag claims (the grace sentence, not just its citation; the high-risk step's basis, not the final class). An unmeasured, transient or missing outcome (corpus gap, lost trace, failed lookup) is counted apart, never as a miss or as "checked". (seen: E6, F7b, X2, V7, B1, E10, 14)
- [ ] *(isolation-auditor)* A test on the committed set asserts the counts, the languages and the Pile B ↔ `commission_b` mapping the DoD states. "Every file validates" also passes with zero items. (seen: B7, B4, 2)
- [ ] *(isolation-auditor)* No new case describes the same specific system as a Pile B example, even when no wording is shared. Read the case against the scenarios, not only the word runs. (seen: X0 via the B4 and X0b audits, 2)
- [ ] Every label-bearing field (`as_of`, `accepted_bases`, …) counts toward label freeze. Duplicate YAML keys are rejected, and a bulk `LABEL_CHANGES` row can't hide unrelated edits. (seen: B5c, B10a, F7b, 3)
