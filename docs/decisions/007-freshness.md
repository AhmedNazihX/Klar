# 007 · Freshness check before the build freezes

- **Date:** 2026-10-01 (Run 1); 2026-10-15 (Run 2, immediately before W1)
- **Story:** W0 (docs/BACKLOG.md); also affects W1, W2, W3, P8b, C2, C3
- **Status:** accepted for Run 1 (the user signed off the Bitkom correction on 2026-10-01; INIT corrected the same day); Run 2
  done 2026-10-15: nothing changed, decision 021 not triggered

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
Run 1 outcome (accepted by the user on 2026-10-01):
- **Guidelines:** still a draft, so decision 021 is not triggered. Nothing to reload, and there is no new story. The
  corpus, the benchmark and the hr-ex numbering from decision 001 stay as they are.
- **Simplified form:** not published. P8b keeps INIT's behaviour: SMEs and SMCs get the full Annex IV skeleton, with
  a note that a simplified form is expected.
- **Bitkom:** cite 69% as "Bitkom Research, 2024 survey of 602 German companies (published 9 September 2024)". It
  comes from the same survey as INIT's 24% / 3% / 24% awareness figures. Don't attribute it to the February 2026
  report. If a 2026 AI Act figure is wanted, use the report's 93% (of the 138 affected companies) or its 56% (of all
  604). The report's method appendix (p. 52) lists the 2024 company survey (n=602, KW 23–30 2024) as a comparison
  dataset ("ausgewählte Ergebnisse aus der Erhebung 2024"), which likely explains INIT's misattribution.

## Run 2 (checked 2026-10-15, before W1)
_Instructions: re-check all three questions immediately before W1 starts, using the same sources, and record the date
checked for each. If the guidelines have been adopted by then, apply decision 021: add the mapping-and-reload story
and note the finalisation date as a limitation on W2 (README). If the simplified tech-doc form has been published by
then, P8b is already built and Run 2 falls at the build freeze (decision 024), so the follow-up is a limitation note
on W2 (README), not a P8b change, unless the user grants an exception to the freeze. For Bitkom, a one-line
re-confirmation is enough: the 2024 press release still carries the 69% figure and no newer Bitkom figure replaces
it._

| # | Question | Answer | Primary source (checked 2026-10-15) |
| --- | --- | --- | --- |
| 1 | High-risk guidelines final? | **No.** Still a draft. The library page is still titled "Draft Commission guidelines on the classification of high-risk AI systems" (published 19 May 2026, last updated 23 July 2026, when the consultation closed). All three downloads are labelled "Draft Guidelines", and the page links to no final version. The consultation page still says the "final guidelines will be adopted by the end of 2026" (last updated 16 June 2026). The guidelines policy page still says "The Commission has developed draft guidelines", and that feedback "is going to be incorporated in the final version of the guidelines before adoption by the Commission". The AI Act page (last updated 3 August 2026) lists the adopted guidelines on prohibited practices, the AI system definition, GPAI and transparency, but none on high-risk classification. A search of the Commission's sites (digital-strategy, ec.europa.eu, AI Act Service Desk) found no adopted version. | [Draft guidelines (library)](https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems); [Targeted consultation](https://digital-strategy.ec.europa.eu/en/consultations/targeted-consultation-draft-guidelines-classification-high-risk-artificial-intelligence-systems); [Guidelines for high-risk systems](https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-high-risk-systems); [Commission AI Act page](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) |
| 2 | Simplified tech-doc form published? | **No.** The AI Act Service Desk's Art. 11 page (consolidated text as at 27 July 2026) still only quotes the duty: "the Commission shall establish a simplified technical documentation form". It links to no form, only to Recitals 66 and 71. The AI Act page (last updated 3 August 2026) mentions "simplified technical documentation requirements" being extended to SMCs, but no published form; the only template it names is the GPAI training-content summary. A web search found no published form. | [AI Act Service Desk, Art. 11](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-11); [Commission AI Act page](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai); [Regulation (EU) 2026/1744, Art. 11(1) as amended](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng) |
| 3 | Bitkom 69% figure | **Confirmed, unchanged.** The 9 September 2024 press release still says "Eine breite Mehrheit von 69 Prozent der Unternehmen braucht nach eigenem Dafürhalten Hilfe bei der Auseinandersetzung mit dem AI Act" (602 companies with 20 or more employees, telephone survey, calendar weeks 23–30 of 2024). Bitkom's newer AI survey (press release of 14 September 2026: 603 companies, calendar weeks 28–33 of 2026) has no figure on needing help with the AI Act, so nothing replaces the 69%. It does report newer AI Act figures, in case a 2026 number is wanted: 37% expect to be affected as deployers (23% a year earlier); 89% of the affected or checking companies expect high implementation effort; 66% of all companies see more disadvantages than advantages (56% a year earlier). | [Bitkom press release, 9 Sep 2024](https://www.bitkom.org/Presse/Presseinformation/Jedes-vierte-Unternehmen-beschaeftigt-mit-AI-Act); [Bitkom press release, 14 Sep 2026](https://www.bitkom.org/Presse/Presseinformation/Erstmals-nutzt-Mehrheit-Unternehmen-KI) |

Run 2 outcome: the guidelines are still a draft, so decision 021 is not triggered (no mapping-and-reload story, no README
limitation for finalisation). The simplified form is not published, so P8b and W2 stay as they are. The Bitkom
citation from Run 1 stands.

## Consequences
- No change to the corpus, the benchmark or decision 001 after Run 1.
- The Bitkom citation in INIT › Problem was corrected on 2026-10-01 (69% credited to the 2024 survey of 602
  companies; the open question marked answered), so the README (W2) and the deck (W3) quote the right source.
- No change after Run 2 (2026-10-15) either: the build freezes on the 19 May 2026 draft guidelines. W1 can start.
- The README (W2) can say the benchmark and corpus use the draft guidelines of 19 May 2026, with final adoption
  expected by the end of 2026 (consultation page), as checked on 2026-10-15.
