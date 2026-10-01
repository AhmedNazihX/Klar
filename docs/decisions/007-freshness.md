# 007 · Freshness check before the build freezes

- **Date:** 2026-10-01 (Run 1); Run 2 is due immediately before W1 starts
- **Story:** W0 (docs/BACKLOG.md); also affects W1, W2, W3, P8b, C2, C3
- **Status:** proposed (Run 1 done 2026-10-01; awaiting the user's sign-off on the Bitkom correction; Run 2 pending before W1)

## Question
INIT › Legal corpus and Open questions list three facts to check before the build freezes (decision 024: the freeze
is when W1 starts):
1. Has the Commission finalised the high-risk classification guidelines? The corpus and the benchmark use the draft
   of 19 May 2026 (decision 001).
2. Has the Commission published the simplified technical documentation form for SMEs and small mid-caps (SMCs)?
3. Does Bitkom's February 2026 AI report say that 69% of companies need help implementing the AI Act, and on what
   sample?

If the guidelines are final, decision 021 applies: the draft benchmark stays frozen, and the final text is loaded
only in a new story that first maps each final example to its draft id and tags Pile B.

## Run 1 (checked 2026-10-01)

| # | Question | Answer | Primary source (checked 2026-10-01) |
| --- | --- | --- | --- |
| 1 | High-risk guidelines final? | **No.** Still a draft. The Commission's library page lists the 19 May 2026 draft and links to no final version. The consultation page says the deadline was extended by four weeks to 23 July 2026 and that the "final guidelines will be adopted by the end of 2026" (page last updated 16 June 2026). The guidelines policy page (last updated 6 July 2026) also describes the draft only. A search of the Commission's sites turned up no adopted version. | [Draft guidelines (library)](https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems); [Targeted consultation](https://digital-strategy.ec.europa.eu/en/consultations/targeted-consultation-draft-guidelines-classification-high-risk-artificial-intelligence-systems); [Guidelines for high-risk systems](https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-high-risk-systems) |
| 2 | Simplified tech-doc form published? | **No.** Art. 11(1) as amended by the Omnibus says "the Commission shall establish a simplified technical documentation form targeted at the needs of SMEs, including start-ups, and SMCs", and that notified bodies must accept it. It sets no deadline. Neither the AI Act page nor the AI Act Service Desk's Art. 11 page links to a form. The AI Act page mentions only that the simplified documentation requirements were extended to SMCs. | [Regulation (EU) 2026/1744, Art. 11(1) as amended](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng) (our parsed copy: `data/parsed/omnibus.en.jsonl`); [AI Act Service Desk, Art. 11](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-11); [Commission AI Act page](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) |
| 3 | Bitkom 69% figure | **The figure is real, but INIT gives the wrong source.** The 69% comes from the **2024** Bitkom Research survey, not the February 2026 report. Its wording: "Eine breite Mehrheit von 69 Prozent der Unternehmen braucht nach eigenem Dafürhalten Hilfe bei der Auseinandersetzung mit dem AI Act." Method: 602 companies with 20 or more employees in Germany, telephone survey, calendar weeks 23–30 of 2024, representative of the whole economy (press release of 9 September 2024). Bitkom repeated the figure on 30 October 2024 ("Mehr als zwei Drittel (69 Prozent) benötigen nach eigenem Bekunden Unterstützung …"). The February 2026 report "Künstliche Intelligenz in Deutschland" (DOI 10.64022/2026-kuenstliche-intelligenz; 604 companies with 20 or more employees, weeks 27–32 of 2025) has no such figure. Its only 69% is the share of the population that prefers AI from Germany (p. 3). On the AI Act it reports that 93% of affected companies (n=138) expect high or very high implementation effort, and that 56% of all companies (n=604) see more disadvantages than advantages (pp. 44–45). | [Bitkom Research, 9 Sep 2024](https://bitkom-research.de/news/jedes-vierte-unternehmen-beschaeftigt-sich-mit-dem-ai-act); [Bitkom press release, 9 Sep 2024](https://www.bitkom.org/Presse/Presseinformation/Jedes-vierte-Unternehmen-beschaeftigt-mit-AI-Act); [Bitkom press release, 30 Oct 2024](https://www.bitkom.org/Presse/Presseinformation/Praxishilfe-Mit-wenigen-Klicks-durch-die-KI-Verordnung-navigieren); [Bitkom report, Feb 2026 (PDF)](https://www.bitkom.org/sites/main/files/2026-02/bitkom-studienbericht-ki.pdf) |

## Decision
Run 1 outcome (proposed; the Bitkom re-attribution awaits the user's sign-off):
- **Guidelines:** still a draft, so decision 021 is not triggered. Nothing to reload, and there is no new story. The
  corpus, the benchmark and the hr-ex numbering from decision 001 stay as they are.
- **Simplified form:** not published. P8b keeps INIT's behaviour: SMEs and SMCs get the full Annex IV skeleton, with
  a note that a simplified form is expected.
- **Bitkom:** cite 69% as "Bitkom Research, 2024 survey of 602 German companies (published 9 September 2024)". It
  comes from the same survey as INIT's 24% / 3% / 24% awareness figures. Don't attribute it to the February 2026
  report. If a 2026 AI Act figure is wanted, use the report's 93% (of the 138 affected companies) or its 56% (of all
  604). The report's method appendix (p. 52) lists the 2024 company survey (n=602, KW 23–30 2024) as a comparison
  dataset ("ausgewählte Ergebnisse aus der Erhebung 2024"), which likely explains INIT's misattribution.

## Run 2 (before W1)
_Pending. Re-check all three questions immediately before W1 starts, using the same sources, and record the date
checked for each. If the guidelines have been adopted by then, apply decision 021: add the mapping-and-reload story
and note the finalisation date as a limitation on W2 (README). If the simplified tech-doc form has been published by
then, P8b is already built and Run 2 falls at the build freeze (decision 024), so the follow-up is a limitation note
on W2 (README), not a P8b change, unless the user grants an exception to the freeze. For Bitkom, a one-line
re-confirmation is enough: the 2024 press release still carries the 69% figure and no newer Bitkom figure replaces
it._

| # | Question | Answer | Primary source (checked YYYY-MM-DD) |
| --- | --- | --- | --- |
| 1 | High-risk guidelines final? | | |
| 2 | Simplified tech-doc form published? | | |
| 3 | Bitkom 69% figure | | |

## Consequences
- No change to the corpus, the benchmark or decision 001 after Run 1.
- The Bitkom citation in INIT › Problem needs correcting before it reaches the README (W2) or the deck (W3). The
  orchestrator makes that change, because INIT is the source of truth and W0 doesn't edit it.
- W1 still depends on W0's Run 2.
