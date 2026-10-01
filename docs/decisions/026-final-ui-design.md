# 026 · The final UI design and how it fits the INIT

- **Date:** 2026-10-01
- **Story:** design (docs/BACKLOG.md › Phase 5 › Design reference); affects P1, P2b, P5–P13, P14–P28, C9, E8, E10, E12, E13, W1, W2, S3
- **Status:** accepted (the user, 2026-10-01, item by item)

## Question
The user's final design has 28 artboards and a refreshed design system:
- canvas "AI Act Classification Assistant — UI/UX", https://claude.ai/artifact/9f2ghnteUy1kbPyUa63PEv, version
  1790857594-402f;
- design system "Klar", https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4, version 1790858064-dcaa (copied to
  `docs/design-system/`).

Mapped against the backlog, the artboards show things the INIT leaves out or rules out. The INIT also asks for
things no artboard shows, and three design details clash with earlier decisions. Which of them does the product
keep, and which stories own them?

## Options
For each item, the options were (A) follow the design as drawn, or adapted as noted, (B) keep both, or a variant,
and (C) drop it or keep it smaller. No numbers were measured: these are product and scope choices. The mapping
report (2026-10-01, sections 1–6) listed the gaps. The user went through them one at a time.

## Decision

**In the design, beyond the INIT**

| # | Item | Choice | Why | Stories |
| --- | --- | --- | --- | --- |
| 1 | Fine tile (ResultProhibited) and the Welcome SME fines line | B: keep both, quoting Art. 99(3)/(6) with a citation; INIT out-of-scope line becomes "National penalty rules" | The Act's own fine maxima are in the corpus; only national rules are out of scope | P18, P21, P16, P17; INIT |
| 2 | Welcome "Where you are established" | A: keep both fields; the hint cites Art. 2(1)(c) and Art. 22 (EU representative), not national authorities; profile values pre-fill the scope follow-up answers | The Act decides what establishment changes; engine scoring stays the same | P18, P5b, P19 |
| 3 | Vendor letters | **B** (changed from A by the user, 2026-10-01): keep all three. "Copy question" as drawn; "Draft a message" (prohibited) and "Draft a request" (ambiguous) become short vendor letters built only from the result's facts (EN/DE, DRAFT label, nothing-invented check) | The next step on those results is a letter to the vendor; the drafting rules already cover it | P28 (new), P21, P22, P5b; INIT Documentation drafting |
| 4 | "Klar re-checks when final" (ResultAmbiguous) | A: drop the promise; list "Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)" under what would settle it | No story watches guidance and re-classifies | P22, E12 |
| 5 | Site pages Method, Privacy, Impressum, Contact | A: all four in the MVP as static pages with marked placeholders; Privacy fills the decided values (30 days, named processors); Contact is a `mailto:` link | Cheap, and the public pages need them; no mail backend | P17, P15, S3 |
| 6 | Q&A history | C: kept only for the browser session (survives a refresh, e.g. sessionStorage); nothing in the database; YourData drops the "Questions asked" count | INIT Storage doesn't list questions; less stored data | P7, P12, P19 |
| 7 | Company profile | A: stored with the inventory (name, staff band, turnover band, establishment, where used; derived SME/SMC), owner-only RLS, 30-day purge, export/delete, named in the privacy notice; not an input to classification | Drives the SME/SMC notes and the sidebar line | P19, P18, P8b, P23, P17; INIT Storage |
| 8 | "Import a list" | A: it is the INIT file import: "Import your data" on Welcome and Inventory restores a file exported from Your data; Your data gets an Import button; no batch classification | Matches INIT Storage (export/import files) | P18, P6, P12, P19 |
| 9 | Duty ticks and progress | A: stored per tool and duty (owner-only, 30-day purge, export); counts per tool and overall; "Klar keeps the list; it doesn't check the work for you" wherever progress shows; the exported checklist shows ticks | The checklist is in the INIT; ticks make it usable | P19, P24, P25; INIT Storage |
| 10 | "Not enough to start" (ClassifyVague) | A: part of the engine. The facts step flags a too-thin description (what it decides or who it affects missing). The engine stops before the four checks with a "needs a description" outcome, a case of needs more information, carrying the three prompts. It is evaluated like everything else; cases like "We use AI for HR" should produce it; the facts recordings are re-recorded once | INIT: the evaluation scores what every user gets, so the check can't live only in the API | E13 (new), P20, P1; decision 010 addendum |
| 11 | Dates under the original text | A: swap only the Art. 113 route dates under the original text (2 Aug 2026 Annex III, 2 Aug 2027 Annex I) on Result, Inventory, Obligations, Ambiguous and the timeline. The duty list stays the amended list, with the notice "Dates follow the original Art. 113. The duties shown are the amended text's." Class and route still come from E11 | Shows the Omnibus's date shift without a second obligations table | P10, P6, P22, P24; decision 020 addendum |
| 12 | Legal review on prohibited results | A: keep the summary line; INIT Ethics line becomes "high-risk, prohibited and ambiguous outcomes" | A ban is the case where advice matters most | E8, P5, P21; INIT Ethics |
| 13 | "If no: Minimal risk" (ResultNeedsInfo) | A: "If no: Not high-risk on this point. The transparency check then decides whether any duties apply."; "If yes" stays as drawn | No class is predicted before the remaining checks run (INIT order) | P5, P5b, E12 |
| 14 | Accuracy on the site after the freeze | A: a data-only exception to decision 024; only the site accuracy file may be written from W1's stored runs, each figure naming its run_id and checked by a test against the final report | The site must show the measured numbers, which exist only after W1 | P27, W1; decision 024 addendum |

**In the INIT, missing from the design**

| # | Item | Choice | Why | Stories |
| --- | --- | --- | --- | --- |
| 15 | Personal-data warning | A: an in-browser check (emails, phone numbers, IBANs, likely person names) shows a Notice under the description field; never blocks; EN and DE; tested; the static hint stays | INIT Ethics asks for a warning; nothing leaves the browser | P12 |
| 16 | Import of data files | Covered by item 8 | Same feature | P12, P6, P18 |
| 17 | Importer, distributor and GPAI-based roles | A: reuse the layouts. Importers and distributors get the deployer-style result with their role sentence and Art. 23/24 duties; a company building on a general-purpose model gets the provider layout plus "The model's maker has its own duties under Chapter V (Art. 53). Klar doesn't assess those." One test each, EN and DE | INIT Roles; no new artboards needed | P5, P23 |
| 18 | Annex I results | A: reuse the needs-information layout: the third-party conformity question naming the product law, quoting Art. 6(1) and the Annex I entry; If yes: High-risk, Annex I, duties from 2 August 2028; If no: "not high-risk on this point; the transparency check then decides"; a test on the recorded Annex I case | INIT Annex I: name the law, ask the decisive question | P5, E12 |
| 19 | Limited-risk, minimal-risk and out-of-scope results | A: the standard result layout (class and role, what to do, facts, how Klar got there, question field). Limited risk shows the Art. 50 duties with a link to the drafted disclosure; minimal risk "No specific duties for this tool" plus Art. 4; out of scope shows why, with the quote and no duty list; a component test per variant on a recorded case, EN and DE; inventory rows link to the tool's own result | INIT Risk classes | P5, P6 |
| 20 | Other documents | A: reuse the two drawn patterns: Art. 50 disclosure texts in the short-notice layout; the Art. 17, Art. 9 and Art. 27 skeletons in the DocSkeleton layout with their own section lists; all on Draft documents with the same statuses | INIT Documentation drafting | P8a, P8b, P9 |
| 21 | Quoted requirement in unfilled sections | A: a Citation (Newsreader, word for word, source line; official German text in DE) above the "To fill in" marker in every unfilled section of Annex IV and the Art. 9/17/27 skeletons. The DocSkeleton line becomes "A simplified form for SMEs and small mid-caps is expected (Art. 11(1)). Until the Commission publishes it, this is the full Annex IV." | INIT asks for it; the old line promised a switch no story owns (same rule as item 4) | P8b, P9 |
| 22 | Small mid-caps | A: Welcome bands: staff 1–9, 10–49, 50–249, 250–749, 750+; turnover up to €10 m, up to €50 m, up to €150 m, more; derived "Counts as an SME" / "Counts as a small mid-cap" / neither; used by the P8b and P23 notes (SMCs get the simplified form; not published yet) | INIT: the Omnibus extends the simplified form to small mid-caps | P18, P19, P8b, P23; INIT Documentation drafting |
| 23 | English-only label | A: on German screens an English-only quote stays in English (Newsreader) with the tag "Amtlicher Text nur auf Englisch verfügbar" and a one-line German explanation; not shown in EN; part of Citation | INIT Ethics (translation errors): never translate the law | P11, P14 |
| 24 | Art. 111(2) legacy marking | A: existing components. The result shows the Art. 111(2) sentence as a Notice under "duties apply from" (plus the per-product caveat for suppliers); marked duties in Result and Obligations show "Only after a significant change" or "From 2 August 2030" with an "Art. 111(2)" tag; the inventory "Applies from" column likewise; the three follow-ups use FactQuestion; EN and DE; a component test on a legacy-marked result | Decision 022; no artboard needed | P5, P6, P24, P5b |

**Clashes with earlier decisions**

| # | Clash | Choice | Why | Stories |
| --- | --- | --- | --- | --- |
| C1 | German "Out of scope" label | A: keep "Außerhalb des Anwendungsbereichs" (user, 2026-09-30); the Design reference notes that the app differs from the system's "Nicht erfasst" | Earlier user decision | P5, P11 |
| C2 | Fonts | A: keep self-hosting through fontsource; P14 adds Lexend 500/600 the same way; nothing goes to Google | No visitor data to Google | P14 |
| C3 | Retention period placeholder | A: fill in "30 days" ("nach 30 Tagen ohne Aktivität") on the privacy notice and the site footer | Decision 013 | P15, P17, P12, P18 |

## Consequences
- **INIT:** out of scope "National penalty rules" (item 1); the Documentation drafting table gains a vendor-letter
  row (item 3); Storage adds a company profile and checklist progress (items 7, 9); the Ethics line covers
  prohibited outcomes (item 12); the simplified-form sentence names SMEs and small mid-caps (item 22).
- **New stories:** P14–P28 (the screens, the site and the vendor letters), C9 (obligation texts for the screens),
  E12 (result fields the screens need) and E13 (the facts step's "needs a description" outcome). P14 and P15
  come before every screen story; W1 depends on E12 and E13, and on the UI stories through P11.
- **Addenda:** decision 010 (a new early end before the checks, item 10), decision 020 (route dates under the
  original text, item 11), decision 024 (the site accuracy file after the freeze, item 14).
- **Not changed:** the engine's scoring (the profile pre-fills answers but isn't a classification input); the
  obligations table stays amended-only (decision 020); no Q&A table; no mail backend.
- E13 writes its own record for the thinness rule and how the metrics score the new outcome.
