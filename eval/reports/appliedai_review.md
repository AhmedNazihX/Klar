# appliedAI disagreement review

The appliedAI cases, their labels and the experts' comments come from the Risk Classification Database of the appliedAI Institute for Europe gGmbH. Credit: "appliedAI Institute for Europe gGmbH", licensed under CC BY 4.0 (<https://creativecommons.org/licenses/by/4.0/>). The comments are quoted as extracted in `eval/appliedai/appliedai.jsonl` (spaces tidied; see `eval/appliedai/SOURCE.md` and decision 002). The experts classified the systems in 2023 against the Commission's 2021 proposal: no Art. 6(3) filter, "Annex II" is today's Annex I.

- Run id: `9908ac9d-3c8c-4e91-be8f-ccdb8b89eb03`
- Benchmark: `appliedai`
- Commit: `ece94328884f61419695b754a3d5883d59964d59`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-14T10:19:45.433024+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.8815, 5838834 tokens
- Cases: 106 (1 failed, 0 not assessed)
- Full metrics: `uv run aiact evaluate report 9908ac9d-3c8c-4e91-be8f-ccdb8b89eb03`

Classifications are guidance, not legal advice.

**How to write a verdict.** Under each disagreement, after `**Verdict:**`, write `engine error`, `outdated label` (the 2023 label no longer fits the law), `label error` (the label didn't fit even the 2021 text, so no change in law explains it, and the engine's answer is right today) or `ambiguous`, then any note of your own (for example `outdated label: Art. 6(3) exempts it`). Keep the mark exactly as written and write only after it; a note line must not start with `#`. Then run `uv run aiact evaluate appliedai-review <run id>` again (from `backend/`): it keeps every verdict and recomputes the accuracy after excluding the outdated and wrong labels. `--check` fails while a disagreement has no verdict.

Matching follows INIT's appliedAI mapping (`score_appliedai`): `low` accepts limited_risk, minimal_risk and out_of_scope (out_of_scope is reviewed all the same); `unclear` matches legally_ambiguous; needs_more_information on an `unclear` case is counted separately, out of accuracy, and reviewed. A not-assessed case (the model provider refused a check, decision 030) is left out of accuracy and of the review, as in the run report.

## Risk-class accuracy

| Cases | Before excluding outdated and wrong labels | After excluding outdated and wrong labels |
| --- | ---: | ---: |
| Every case | 63.0% (51/81) | 78.5% (51/65) |
| Without the Annex I cases | 65.4% (51/78) | 81.0% (51/63) |
| Annex I cases only | 0.0% (0/3) | 0.0% (0/2) |

Verdicts: 56 of 56 disagreements (engine error 9, outdated label 8, label error 21, ambiguous 18).
Left out of the after column: 29 labels, 8 outdated by later law (`outdated label`) and 21 wrong when made (`label error`).

Counted separately (needs_more_information on an `unclear` case): 25.

## By appliedAI function

appliedAI's own enterprise function (the `function:*` tag), Annex I cases included.

| Function | Cases | Disagreements | Before excluding outdated and wrong labels | After excluding outdated and wrong labels |
| --- | ---: | ---: | ---: | ---: |
| accounting_and_finance | 10 | 8 | 28.6% (2/7) | 66.7% (2/3) |
| customer_service | 14 | 7 | 63.6% (7/11) | 77.8% (7/9) |
| human_resource_management | 10 | 3 | 70.0% (7/10) | 70.0% (7/10) |
| it_and_security | 11 | 10 | 12.5% (1/8) | 25.0% (1/4) |
| law | 10 | 6 | 57.1% (4/7) | 100.0% (4/4) |
| logistics_and_supply_chains | 11 | 6 | 71.4% (5/7) | 71.4% (5/7) |
| marketing_sales | 14 | 2 | 92.3% (12/13) | 92.3% (12/13) |
| production_and_manufacturing | 9 | 7 | 50.0% (3/6) | 60.0% (3/5) |
| purchase | 8 | 2 | 85.7% (6/7) | 100.0% (6/6) |
| research_and_development | 9 | 5 | 80.0% (4/5) | 100.0% (4/4) |

## Cases (without Annex I)

| Case | Function | Experts | Engine | Match | Review | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| aai-001 | human_resource_management | high | high_risk, decided, annex:III:4:a | yes |  |  |
| aai-002 | human_resource_management | high | high_risk, legally_ambiguous, annex:III:4:a | yes |  |  |
| aai-003 | human_resource_management | high | high_risk, legally_ambiguous, annex:III:4:b | yes |  |  |
| aai-004 | human_resource_management | high | high_risk, decided, annex:III:4:b | yes |  |  |
| aai-005 | human_resource_management | high | high_risk, decided, annex:III:4:a | yes |  |  |
| aai-006 | human_resource_management | high | high_risk, decided, annex:III:4:a | yes |  |  |
| aai-007 | human_resource_management | high | limited_risk, needs_more_information | no | yes | ambiguous |
| aai-008 | human_resource_management | unclear | limited_risk, decided | no | yes | ambiguous |
| aai-009 | human_resource_management | high | high_risk, decided, annex:III:4:a | yes |  |  |
| aai-010 | human_resource_management | high | prohibited, needs_more_information, annex:III:4:a | no | yes | engine error |
| aai-012 | production_and_manufacturing | low | minimal_risk, legally_ambiguous | yes |  |  |
| aai-013 | production_and_manufacturing | low | minimal_risk, decided | yes |  |  |
| aai-015 | production_and_manufacturing | low | high_risk, needs_more_information, annex:I:B:21 | no | yes | engine error |
| aai-019 | production_and_manufacturing | low | out_of_scope, decided | yes | yes | ambiguous |
| aai-020 | production_and_manufacturing | unclear | limited_risk, decided | no | yes | outdated label |
| aai-025 | purchase | unclear | minimal_risk, decided | no | yes | label error |
| aai-026 | purchase | low | minimal_risk, decided | yes |  |  |
| aai-027 | purchase | low | limited_risk, decided | yes |  |  |
| aai-028 | purchase | low | minimal_risk, decided | yes |  |  |
| aai-029 | purchase | unclear | limited_risk, needs_more_information | counted separately | yes | label error |
| aai-030 | purchase | low | minimal_risk, decided | yes |  |  |
| aai-031 | purchase | low | minimal_risk, needs_more_information | yes |  |  |
| aai-032 | purchase | low | minimal_risk, needs_more_information | yes |  |  |
| aai-033 | customer_service | low | limited_risk, decided | yes |  |  |
| aai-034 | customer_service | unclear | high_risk, needs_more_information, annex:III:4:b | counted separately | yes | ambiguous |
| aai-035 | customer_service | high | minimal_risk, needs_more_information | no | yes | ambiguous |
| aai-036 | customer_service | high | high_risk, decided, annex:III:1:a | yes |  |  |
| aai-037 | customer_service | unclear | minimal_risk, needs_more_information | counted separately | yes | label error |
| aai-039 | customer_service | unclear | minimal_risk, needs_more_information | counted separately | yes | outdated label |
| aai-040 | customer_service | low | limited_risk, needs_more_information | yes |  |  |
| aai-041 | customer_service | low | minimal_risk, needs_more_information | yes |  |  |
| aai-042 | customer_service | high | failed (no result) | no (failed) | yes | engine error |
| aai-043 | customer_service | low | minimal_risk, decided | yes |  |  |
| aai-044 | customer_service | unclear | limited_risk, decided | no | yes | label error |
| aai-045 | customer_service | low | limited_risk, decided | yes |  |  |
| aai-046 | customer_service | high | minimal_risk, decided | no | yes | outdated label |
| aai-049 | customer_service | low | minimal_risk, decided | yes |  |  |
| aai-053 | law | unclear | high_risk, needs_more_information, annex:III:8:a | counted separately | yes | ambiguous |
| aai-054 | law | unclear | minimal_risk, decided | no | yes | label error |
| aai-055 | law | high | limited_risk, needs_more_information | no | yes | label error |
| aai-056 | law | low | limited_risk, legally_ambiguous | yes |  |  |
| aai-057 | law | unclear | minimal_risk, decided | no | yes | label error |
| aai-058 | law | unclear | limited_risk, needs_more_information | counted separately | yes | label error |
| aai-059 | law | low | minimal_risk, needs_more_information | yes |  |  |
| aai-060 | law | low | minimal_risk, needs_more_information | yes |  |  |
| aai-061 | law | unclear | minimal_risk, needs_more_information | counted separately | yes | label error |
| aai-062 | law | low | minimal_risk, decided | yes |  |  |
| aai-063 | marketing_sales | low | limited_risk, needs_more_information | yes |  |  |
| aai-064 | marketing_sales | low | limited_risk, decided | yes |  |  |
| aai-065 | marketing_sales | low | minimal_risk, needs_more_information | yes |  |  |
| aai-066 | marketing_sales | low | limited_risk, needs_more_information | yes |  |  |
| aai-068 | marketing_sales | low | minimal_risk, decided | yes |  |  |
| aai-069 | marketing_sales | low | minimal_risk, decided | yes |  |  |
| aai-070 | marketing_sales | low | minimal_risk, needs_more_information | yes |  |  |
| aai-071 | marketing_sales | low | minimal_risk, decided | yes |  |  |
| aai-072 | marketing_sales | low | minimal_risk, needs_more_information | yes |  |  |
| aai-073 | logistics_and_supply_chains | low | minimal_risk, decided | yes |  |  |
| aai-074 | logistics_and_supply_chains | unclear | limited_risk, needs_more_information | counted separately | yes | outdated label |
| aai-075 | logistics_and_supply_chains | unclear | high_risk, decided, annex:III:4:b | no | yes | ambiguous |
| aai-076 | logistics_and_supply_chains | unclear | minimal_risk, needs_more_information | counted separately | yes | outdated label |
| aai-078 | logistics_and_supply_chains | low | limited_risk, needs_more_information | yes |  |  |
| aai-079 | logistics_and_supply_chains | low | minimal_risk, decided | yes |  |  |
| aai-080 | logistics_and_supply_chains | low | minimal_risk, needs_more_information | yes |  |  |
| aai-083 | logistics_and_supply_chains | low | minimal_risk, decided | yes |  |  |
| aai-084 | it_and_security | unclear | limited_risk, needs_more_information | counted separately | yes | label error |
| aai-085 | it_and_security | low | minimal_risk, decided | yes |  |  |
| aai-086 | it_and_security | unclear | minimal_risk, needs_more_information | counted separately | yes | ambiguous |
| aai-087 | it_and_security | unclear | minimal_risk, decided | no | yes | label error |
| aai-088 | it_and_security | high | minimal_risk, decided | no | yes | ambiguous |
| aai-090 | it_and_security | unclear | minimal_risk, decided | no | yes | label error |
| aai-091 | it_and_security | low | high_risk, needs_more_information, annex:III:2 | no | yes | engine error |
| aai-092 | it_and_security | high | minimal_risk, decided | no | yes | label error |
| aai-093 | it_and_security | prohibited | high_risk, needs_more_information, annex:III:1:a | no | yes | engine error |
| aai-094 | it_and_security | unclear | minimal_risk, decided | no | yes | label error |
| aai-095 | research_and_development | low | minimal_risk, needs_more_information | yes |  |  |
| aai-098 | research_and_development | low | limited_risk, needs_more_information | yes |  |  |
| aai-099 | research_and_development | unclear | limited_risk, needs_more_information | counted separately | yes | outdated label |
| aai-102 | research_and_development | low | minimal_risk, decided | yes |  |  |
| aai-104 | research_and_development | low | minimal_risk, decided | yes |  |  |
| aai-105 | accounting_and_finance | unclear | minimal_risk, needs_more_information | counted separately | yes | ambiguous |
| aai-106 | accounting_and_finance | unclear | minimal_risk, decided | no | yes | label error |
| aai-107 | accounting_and_finance | high | minimal_risk, decided | no | yes | label error |
| aai-108 | accounting_and_finance | unclear | minimal_risk, decided | no | yes | outdated label |
| aai-109 | accounting_and_finance | unclear | high_risk, decided, annex:III:4:b | no | yes | ambiguous |
| aai-110 | accounting_and_finance | unclear | high_risk, needs_more_information, annex:III:5:b | counted separately | yes | ambiguous |
| aai-111 | accounting_and_finance | high | high_risk, decided, annex:III:5:b | yes |  |  |
| aai-112 | accounting_and_finance | unclear | minimal_risk, decided | no | yes | label error |
| aai-113 | accounting_and_finance | high | high_risk, legally_ambiguous, annex:III:5:b | yes |  |  |
| aai-114 | accounting_and_finance | unclear | high_risk, needs_more_information, annex:III:4:b | counted separately | yes | ambiguous |
| aai-115 | marketing_sales | low | minimal_risk, decided | yes |  |  |
| aai-116 | marketing_sales | unclear | prohibited, needs_more_information, annex:III:4:b | counted separately | yes | engine error |
| aai-117 | marketing_sales | low | limited_risk, needs_more_information | yes |  |  |
| aai-118 | marketing_sales | low | minimal_risk, needs_more_information | yes |  |  |
| aai-119 | marketing_sales | low | prohibited, needs_more_information | no | yes | engine error |

## Annex I cases (reported separately)

Cases the experts linked to Annex II of the 2021 proposal (today's Annex I, the product legislation route), tagged `annex_i`. They are reported apart from the other cases.

| Case | Function | Experts | Engine | Match | Review | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| aai-011 | production_and_manufacturing | unclear | minimal_risk, needs_more_information | counted separately | yes | ambiguous |
| aai-016 | production_and_manufacturing | unclear | high_risk, needs_more_information, annex:III:2 | counted separately | yes | engine error |
| aai-017 | production_and_manufacturing | unclear | minimal_risk, decided | no | yes | ambiguous |
| aai-024 | production_and_manufacturing | unclear | limited_risk, needs_more_information | counted separately | yes | label error |
| aai-077 | logistics_and_supply_chains | unclear | high_risk, needs_more_information, annex:I:B:20 | counted separately | yes | engine error |
| aai-081 | logistics_and_supply_chains | unclear | minimal_risk, needs_more_information | counted separately | yes | ambiguous |
| aai-082 | logistics_and_supply_chains | unclear | minimal_risk, decided | no | yes | ambiguous |
| aai-089 | it_and_security | unclear | limited_risk, needs_more_information | counted separately | yes | ambiguous |
| aai-096 | research_and_development | unclear | limited_risk, needs_more_information | counted separately | yes | label error |
| aai-100 | research_and_development | unclear | out_of_scope, decided | no | yes | outdated label |
| aai-101 | research_and_development | unclear | minimal_risk, needs_more_information | counted separately | yes | label error |
| aai-103 | research_and_development | unclear | minimal_risk, needs_more_information | counted separately | yes | label error |

## Disagreements (44)

### Case aai-007

- Function: human_resource_management
- Experts: high
- Engine: limited_risk, needs_more_information
- Match: no
- Look first at: high_risk (expected high_risk, got limited_risk (needs_more_information))
- Experts' comment: "High risk due to the task allocation component. Additionally, aspects of monitoring and evaluating performance or behavior might apply." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Schritt-für-Schritt-Anleitungen werden als Ausgaben genannt, aber es bleibt offen, ob das System sie erzeugt oder vorhandene interne Inhalte lediglich wiedergibt. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: The staffing sentence is peripheral, but the engine's high-risk step says "Es wurde keine Verwendung nach Anhang III gefunden" without addressing it. If you treat the staffing feature as part of the intended purpose, this becomes an engine error.

### Case aai-008

- Function: human_resource_management
- Experts: unclear
- Engine: limited_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got limited_risk (decided))
- Experts' comment: "Unclear, as this use case may be seen as nudging people to sign up for certain types of training to advance in their career." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Plattform wird als KI-gestützt beschrieben und sagt zukünftige Lernanforderungen voraus, um personalisierte Empfehlungen zu erstellen. Mangels gegenteiliger Angaben wird ein Bezug zur Union angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System wertet individuelle Lernbedürfnisse und Lernverläufe aus, um Lernangebote für die berufliche Weiterbildung zu empfehlen; die Beschreibung nennt keine kontextfremde oder ungerechtfertigte beziehungsweise unverhältnismäßige Schlechterstellung.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 1, Art. 50 Abs. 2. Der Lern-Chatbot beantwortet Fragen von Lernenden und interagiert daher direkt mit natürlichen Personen; der beschriebene Einsatz lässt nicht erkennen, dass für diese Personen offensichtlich ist, dass sie mit einem KI-System interagieren. Der Chatbot erzeugt textliche Antworten; die Empfehlungen allein wären keine synthetischen Inhalte, aber für die Antworten ist keine Ausnahme für Standardbearbeitung oder eine nicht wesentliche Veränderung von Eingabedaten beschrieben. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: The experts' "unclear" fits, and the engine's *decided* limited_risk does not engage 3(b) at all. If you take the narrow "institution" reading, choose outdated label instead.

### Case aai-010

- Function: human_resource_management
- Experts: high
- Engine: prohibited, needs_more_information, annex:III:4:a
- Match: no
- Look first at: prohibited (expected high_risk, got prohibited (needs_more_information))
- Experts' comment: "High risk, as the System is used for the recruitment or selection of natural persons and to evaluate candidates." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt maschinelles Lernen und statistische Methoden, um Vorhersagen über Bewerber:innen zu erstellen. Ein Bezug zur Union wird mangels entgegenstehender Angaben angenommen.
- Engine, prohibited (needs_more_information): Das System bewertet emotionale Eigenschaften von Bewerber:innen im Recruiting; die Beschreibung sagt jedoch nicht, ob es diese aus biometrischen Daten ableitet. Bis zur Antwort auf diese Frage wird ein Verbot nach Art. 5 Abs. 1 Buchst. f angenommen: Erkennt das System Gefühle oder Absichten von Menschen, etwa Stress, Frust oder Langeweile, zum Beispiel aus Gesicht, Stimme, Tippverhalten oder anderen Körpersignalen?
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe a aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 1. Bewerber:innen interagieren unmittelbar mit dem System, indem sie während der Bewerbung Spiele darin spielen; es gibt keinen Hinweis, dass die Interaktion für sie offensichtlich als KI-Interaktion erkennbar ist.

**Verdict:** engine error: Annex III 4(a): game-based candidate screening is high-risk. Art. 5(1)(f) needs emotions inferred from biometric data (Art. 3(39)); game results and dispositional "emotional traits" are neither, so assuming a prohibition is unsupported.

### Case aai-015

- Function: production_and_manufacturing
- Experts: low
- Engine: high_risk, needs_more_information, annex:I:B:21
- Match: no
- Look first at: high_risk (expected minimal_risk, got high_risk (needs_more_information))
- Experts' comment: none
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Der Anlagenoptimierer leitet mithilfe von Prozessdaten, neuronalen Netzen und anderen Algorithmen ab, wie er Parameter autonom anpasst. Es wird angenommen, dass das System in der EU eingesetzt wird oder seine Ergebnisse dort genutzt werden.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (needs_more_information): Bis zur Antwort auf diese Frage wird Hochrisiko über Anhang I angenommen: Wird das Produkt mit einer Zweckbestimmung in Verkehr gebracht oder in Betrieb genommen, die es unter Verordnung (EU) 2023/1230 über Maschinen fallen lässt?
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** engine error: Art. 6(1): a throughput autopilot for a cement mill has no safety function (Annex I guidelines para 37, 42), and Reg. 2023/1230 (Annex I B:21) requires third-party assessment only for ML that ensures safety functions. Defaulting to high is unsupported; the experts' low is right.

### Case aai-019

- Function: production_and_manufacturing
- Experts: low
- Engine: out_of_scope, decided
- Match: yes
- Experts' comment: none
- Engine, scope (decided): Nicht anwendbar: Die KI-Verordnung gilt nicht. Art. 3 Nr. 1: Es ist kein KI-System, weil es nicht aus den erhaltenen Eingaben ableitet, wie es seine Ausgaben erzeugt (Erwägungsgrund 12).

**Verdict:** ambiguous: Both answers score as `low` (`low` accepts out_of_scope), so this is a review of a match, not a disagreement. The engine's out_of_scope is the better reading of the text. Of the three words, `ambiguous` is the only one that is not false *and* keeps the case counted: `outdated label` would drop a correct match from…

### Case aai-020

- Function: production_and_manufacturing
- Experts: unclear
- Engine: limited_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got limited_risk (decided))
- Experts' comment: "Unclear, if the planning AI can be seen as task allocation, because truck drivers will act accordingly." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Der Assistent nutzt maschinelles Lernen, um aus Eingaben Informationen zu verarbeiten und Ausgaben zu erzeugen; damit ist er ein KI-System. Es wird angenommen, dass das System in der EU eingesetzt oder dort auf den Markt gebracht wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 1, Art. 50 Abs. 2. Fahrer:innen nutzen den Assistenten über Webkanäle und eine mobile App und fragen ihn zum Ladungsstatus; es ist nicht offensichtlich, dass sie mit einem KI-System interagieren. Der Assistent erzeugt vermutlich natürlichsprachige Antworten zum Ladungsstatus und damit synthetischen Text; eine Ausnahme für Standardbearbeitung oder eine nicht wesentliche Änderung ist nicht ersichtlich. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** outdated label: both reviews: The truck-pickup scheduling assistant allocates by load and dock availability, not by the drivers' behaviour or traits (Annex III 4(b), G-p269/272). The drivers are probably not the deployer's workers either. The 2021 "task allocation" was unqualified, so the doubt then had a hook.

### Case aai-025

- Function: purchase
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "The AI System may be high-risk e.g. if the supply chain was in the context of critical infrastructure e.g. supply of gas via trucks." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die ML-basierte Recommender-Engine analysiert Daten und leitet daraus relevante Informationen und Warnungen ab. Der Anbieter wird als Münchner Unternehmen beschrieben.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: News-based supply-chain risk alerts for a car-parts supplier. These are neither a safety component (Recital 55: "directly protect physical integrity") nor a critical-infrastructure deployer (G-p196/200). The experts reasoned about a hypothetical other deployment, and the 2021 Annex III 2 also required a safety…

### Case aai-029

- Function: purchase
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI System is intended to detect anomalies that may represent fraud, hence the AI might be seen as being used for "making individual risk assessments of natural persons in order to assess the risk of a natural person for offending"" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet Anomalien aus Daten und Feedback ab, statt ausschließlich feste, von Menschen definierte Regeln auszuführen. Ein Unionsbezug wird angenommen, da die Beschreibung keinen Hinweis auf einen ausschließlich außereuropäischen Bezug enthält.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das Dashboard zeigt strukturierte Anomalieanalysen; ob die automatisch versandte Anomalie-E-Mail darüber hinaus synthetischen Text erzeugt, ist nicht beschrieben. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: Order and warehouse anomaly dashboard at a food distributor. It works on transactions, not natural persons, and isn't used by or on behalf of law enforcement (Annex III 6(d), G-p81/356). The 2021 6(a) required use "by law enforcement authorities".

### Case aai-034

- Function: customer_service
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:III:4:b
- Match: counted separately
- Experts' comment: "The Ai-based routing is based on the predicted intention of the calling customer and the characteristics of the call-agent, thereby allocating a task (to handle a call) on the basis of the characteristics of the call agent" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Calls go to the "leistungsstärksten Agent:innen". If that means individual performance scores, this is task allocation on behavioural traits (G-p269–270, G-ex130) and profiling, which Art. 6(3) cannot exempt, so the answer is high, not unclear. "Unclear" holds only if routing uses skills or language tags alone…

### Case aai-035

- Function: customer_service
- Experts: high
- Engine: minimal_risk, needs_more_information
- Match: no
- Look first at: high_risk (expected high_risk, got minimal_risk (needs_more_information))
- Experts' comment: "High Risk, as the System is used for Remote biometric identification (using the voice of customers who call the company)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System wird als KI beschrieben und nutzt einen Stimmabdruck zur Identifizierung und Authentifizierung; nichts in der Beschreibung weist auf eine bloße Ausführung ausschließlich menschlich festgelegter Regeln hin. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Voice prints are used "zur Identifizierung und Authentifizierung" passively during the whole call. Confirming a caller for access to a service is excluded (Annex III 1(a), Recital 54, G-p136/138). It would be remote biometric identification only if the voice print is matched 1:N against a database without the…

### Case aai-037

- Function: customer_service
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "It may be used for High-risk applications e.g. in the context of law enforcement" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt NLP und maschinelles Lernen, um Eingaben kontextbezogen zu verstehen und daraus strukturierte Ausgaben zu erzeugen. Ein Unionsbezug ist nicht angegeben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: General document extraction for business processes. "May be used" in law enforcement is not the intended purpose (Art. 3(12)), and the 2021 Annex III 6 also attached to intended use by law enforcement.

### Case aai-039

- Function: customer_service
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI is providing informations and suggestions for next steps based on the past customer cases a call-agent has handled, thereby being involved in task allocation based on individual behaviour" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das IDSS nutzt Machine Learning und lernt aus früheren Fällen; es leitet daraus Vorschläge für Handlungsoptionen ab. Es wird angenommen, dass das System in der EU eingesetzt oder dort auf den Markt gebracht wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** outdated label: both reviews: Next-best-action support for resolving customer issues. It neither allocates tasks among workers on their traits nor monitors or evaluates their performance (4(b), G-p278, G-ex135). The unqualified 2021 "task allocation" gave a thin hook.

### Case aai-042

- Function: customer_service
- Experts: high
- Engine: failed (no result)
- Match: no (failed)
- Look first at: no result (the classifier failed) (no result)
- Experts' comment: "High Risk, as the System is used for Remote biometric identification (using the voices of incoming calls)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)

**Verdict:** engine error: the classifier failed (the scope step's reply was cut off twice); the description is answerable

### Case aai-044

- Function: customer_service
- Experts: unclear
- Engine: limited_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got limited_risk (decided))
- Experts' comment: "The AI is giving instructions in recipies based on personal preferences, hence the AI may be seen to perform task allocation" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. KiM nutzt NLP und maschinelles Lernen, verarbeitet damit Eingaben und erstellt Rezeptempfehlungen sowie Antworten. Ein konkreter Unionsbezug wird nicht genannt; mangels gegenteiliger Hinweise wird ein Unionsbezug angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 1, Art. 50 Abs. 2. KiM tauscht sich direkt mit Kund:innen aus; bei diesem Kundenangebot ist nicht offensichtlich, dass sie mit einem KI-System interagieren. KiM erzeugt Text, indem es Fragen zum Kochen beantwortet; eine Ausnahme für unterstützende Standardbearbeitung oder eine nicht wesentliche Änderung von Eingabedaten ist nicht ersichtlich. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: MAGGI recipe chatbot for consumers. There is no work-related relationship, so 4(b) can't apply under any version.

### Case aai-046

- Function: customer_service
- Experts: high
- Engine: minimal_risk, decided
- Match: no
- Look first at: high_risk (expected high_risk, got minimal_risk (decided))
- Experts' comment: "High Risk, as the System is used for Remote biometric identification (using the voices of incoming calls)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System wird als KI-basierte Sprachbiometrie beschrieben und leitet anhand der Stimme eine Authentifizierungsentscheidung ab. Ein Unionsbezug wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** outdated label: both reviews: The bank's IVR authenticates callers "before they reach an agent", which is verification only (Art. 3(36), Annex III 1(a) carve-out, Recital 54, G-p138). That carve-out and Recital 54 were added after 2021. The 2021 Annex III 1(a) covered "remote biometric identification" without an explicit verification exclusion.

### Case aai-053

- Function: law
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:III:8:a
- Match: counted separately
- Experts' comment: "The AI is making individual risk assessments of natural persons in order to assess the risk of a natural person for offending, though it is unclear if the use by Delloite counts as "on behalf of law enforcement authority"" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. TAX-I nutzt maschinelles Lernen, um aus eingegebenen Falldaten Muster zu erkennen und Entscheidungsprognosen sowie Zusammenfassungen zu erstellen. Ein Bezug zur Union wird angenommen, da die Beschreibung weder einen solchen Bezug ausschließt noch auf einen Ort außerhalb der Union hindeutet.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (needs_more_information): Bis zur Antwort auf diese Frage wird Hochrisiko über Anhang III angenommen: Wird das System von einer Justizbehörde oder in ihrem Auftrag oder in der alternativen Streitbeilegung eingesetzt?
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 2. TAX-I erstellt Zusammenfassungen von Fällen und erzeugt damit synthetischen Text; eine Ausnahme für Standardbearbeitung oder eine nicht wesentliche Veränderung greift nicht. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: The description never names the deployer, and the engine asked exactly the deciding question ("Wird das System von einer Justizbehörde oder in ihrem Auftrag ... eingesetzt?"). It is counted separately in any case.

### Case aai-054

- Function: law
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Unclear, if and against which law the information by the AI is being assessed" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Der Bot lernt aus Rückmeldungen und verbessert dadurch seine Vorhersagen; er ist ein KI-System. Ein Unionsbezug wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: IFRS 16 lease-data extraction for a company's accounting. Annex III 8(a) needs use by or on behalf of a judicial authority or an ADR body (G-p414–416). The 2021 8(a) also needed a judicial authority.

### Case aai-055

- Function: law
- Experts: high
- Engine: limited_risk, needs_more_information
- Match: no
- Look first at: high_risk (expected high_risk, got limited_risk (needs_more_information))
- Experts' comment: "High Risk, as the AI System interprets both facts (=the input of clients) and the law (=implemented in generic contract templates) to recommend specific contract templates" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erstellt anhand der Nutzerantworten maßgeschneiderte Vertragstexte; dies ist keine bloße Standardbearbeitung oder unwesentliche Änderung. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: A law firm's self-service contract generator for start-ups. Parties and their lawyers are not "on behalf of a judicial authority" (G-p416). The 2021 8(a) required "assist a judicial authority".

### Case aai-057

- Function: law
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "AI is used to predict whether someone is committing an offence or is likely to be the victim, unclear if a law firm counts as “on behalf of an authority”" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Software wird als KI-gestützt beschrieben und sagt Ergebnisse von Rechtsszenarien voraus. Es wird angenommen, dass das System in der EU genutzt oder dort bereitgestellt wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Outcome prediction for a tax law firm's own case strategy. A party's lawyer is excluded from 8(a) (G-p416), the firm is not law enforcement (6(d), G-p81), and tax disputes are not offences. The 2021 text required use "by" law enforcement or judicial authorities.

### Case aai-058

- Function: law
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "If missing a deadline is an offence, then the AI is making individual risk assessments of natural persons in order to assess the risk of a natural person for offending" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System wird als KI zur Analyse bestehender Vereinbarungen beschrieben; nichts deutet darauf hin, dass es lediglich festgelegte Regeln ausführt. Ein Bezug zur Union ist nicht beschrieben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Die Beschreibung nennt Analysen sowie Warn- und Benachrichtigungsfunktionen, lässt aber offen, ob die Lösung dabei synthetische Texte verfasst oder nur strukturierte Ergebnisse und Hinweise ausgibt. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: Contract-renewal deadline alerts. Missing a supplier deadline is not an offence, and the deployer is not law enforcement (6(d), G-p356/366). Foreclosed under the 2021 text too.

### Case aai-061

- Function: law
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI is suggesting which documents are relevant in the context of a given legal case, it may be interpretet as “making an assessment if the reliability of evidence”" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: e-Discovery used by a litigant NGO. 6(c) requires law enforcement in a criminal investigation (G-p363), and 8(a) excludes parties (G-p416). The 2021 6(d) and 8(a) had the same actor limits.

### Case aai-074

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Unclear, as the training data includes political reports to predict safety critical situations in the management of road traffic" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt maschinelles Lernen, um Vorhersagen zu erstellen und Empfehlungen für Flottenmanager:innen und Fahrer:innen abzuleiten. Die Beschreibung nennt keinen Unionsbezug und weist auch nicht auf einen Bezug ausschließlich außerhalb der Union hin.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System gibt Empfehlungen aus, aber es ist nicht beschrieben, ob diese als generierter Text oder nur als strukturierte Analyse ausgegeben werden. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** outdated label: both reviews: Linde's fleet trip-risk advice. "Road traffic" now means road authorities or ITS operators identified as critical entities (G-p195–196), and an accident-risk predictor is not 6(a) (G-ex195). Linde's industrial gases are not "supply of gas" (G-p199). The 2021 "management and operation of road traffic" lacked that…

### Case aai-075

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: high_risk, decided, annex:III:4:b
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got high_risk (decided))
- Experts' comment: "Unclear, as the training data includes politics reports to predict safety critical situations in the management of road traffic" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das als KI-System beschriebene System erkennt anhand seiner Eingaben Signale und erzeugt daraufhin Audiohinweise sowie Aufzeichnungen. Es wird angenommen, dass das System in der EU eingesetzt oder dort auf den Markt gebracht wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System erfasst fortlaufend individuelles Fahrverhalten; die beschriebenen Hinweise und Prüfungen betreffen dieses Fahrverhalten und weisen nicht auf kontextfremde oder unverhältnismäßige Schlechterstellung hin.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 1, Art. 50 Abs. 2. Das System richtet Audiohinweise an Fahrer:innen und interagiert damit direkt; der beschriebene Kontext macht die KI-Natur für sie nicht offensichtlich. Das System erzeugt Audiohinweise; eine Ausnahme für Standardbearbeitung, eine nicht wesentliche Veränderung von Eingabedaten oder eine gesetzliche Straftatgenehmigung ist nicht beschrieben. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: Amazon reviews the footage and supervisors act on it, so "purely and exclusively for safety" is hard to sustain. The experts' comment (road traffic) was copied from aai-074 and does not address this case. If you agree high is clearly right, choose outdated label.

### Case aai-076

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Unclear, as the AI predicts the demand of consumers (=characteristics) and suggests optimized delivery amounts and routs to the truck drivers (task allocation)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** outdated label: both reviews: CO2-cylinder demand forecasting and delivery plans for pubs. The customers are businesses, and routes are assigned on demand and geography, not driver traits (G-p272). The 2021 unqualified "task allocation" gave the doubt a basis.

### Case aai-084

- Function: it_and_security
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "If the AI is also used to protect the safety of sales people, then it might be seen to assess the risk of a natural person to become a potential victims of criminal offences" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erzeugt Warnungen und automatisierte Tickets; offen bleibt, ob diese nur strukturierte Erkennungsergebnisse wiedergeben oder vom System verfasste Texte enthalten. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: Intrusion detection at a furniture maker. 6(a) concerns natural persons as crime victims, assessed by or on behalf of law enforcement (G-p356). The note's sales-staff idea isn't in the description, and the 2021 6(a) also required use by law enforcement.

### Case aai-086

- Function: it_and_security
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Not sure, if this case counts as on behalf of an authority, but it involves "the risk for for a natural person to become a potential victims of criminal offences" and "detect the emotional state of a natural person" if the crowd gets aggresive, for instance" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System wird als KI-gestützte Analyse beschrieben, die aus Sensordaten Bewegungsmuster und Vorfälle erkennt. Es wird angenommen, dass das System in der EU eingesetzt oder dort auf den Markt gebracht wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Stadium flow analytics (congestion, heatmaps, "Fanpfade", "unbefugter Zugang") from cameras, LiDAR and WiFi. The 6(a) route fails (no law-enforcement actor, G-p81/356). The label holds only if individual paths are tracked by biometric re-identification against a reference set (1(a), G-p135) or aggression is inferred…

### Case aai-087

- Function: it_and_security
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Unclear, as the AI is used to protect the safety of digital infrastructure, which may also include critical digital infrastructure" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Plattform nutzt maschinelles Lernen, um aus Netzwerk-Metadaten Angriffe zu erkennen und zu priorisieren; sie leitet damit Ausgaben aus Eingaben ab. Es wird angenommen, dass die Plattform in der EU eingesetzt oder dort auf den Markt gebracht wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Network threat detection at a commodity trader. It is used solely for cybersecurity, so it is not a safety component (Recital 55, G-p187, G-ex073), and the deployer is not a critical entity (G-p194). "Critical digital infrastructure" wasn't in the 2021 Annex III 2.

### Case aai-088

- Function: it_and_security
- Experts: high
- Engine: minimal_risk, decided
- Match: no
- Look first at: high_risk (expected high_risk, got minimal_risk (decided))
- Experts' comment: "The AI is used to protect the digital infrastructure of an energy provider, which counts as critical infrastructure itself" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Plattform leitet aus Daten mittels maschinellen Lernens Muster ab und erkennt anomales Verhalten. Ein Bezug zur Union ist nicht angegeben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Die Plattform bildet Verhaltensmuster einzelner Benutzer über die Zeit ab und erkennt Abweichungen; die beschriebenen Ausgaben dienen der Cyberabwehr und führen nicht zu einer beschriebenen Schlechterstellung in einem anderen Kontext oder zu einer ungerechtfertigten beziehungsweise unverhältnismäßigen Behandlung.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): The experts' route fails: the Energy Saving Trust is an energy-efficiency body, not an energy supplier, and cybersecurity-only monitoring is out even for grid operators (Recital 55, G-ex073). The alternative route: it models "das Verhalten jedes … Benutzers" and insider threats, which counts as employee risk…

### Case aai-090

- Function: it_and_security
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "The AI is used to protect the safety of digital infrastructure, which may also include critical digital infrastructure" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet offenbar aus verfügbaren Daten Risikobewertungen und Schwachstellenmeldungen ab. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Vulnerability management at an accounting and advisory firm. It is used solely for cybersecurity (Recital 55, G-p187), and the deployer is not critical digital infrastructure (G-p193–194). The 2021 Annex III 2 had no digital infrastructure.

### Case aai-091

- Function: it_and_security
- Experts: low
- Engine: high_risk, needs_more_information, annex:III:2
- Match: no
- Look first at: high_risk (expected minimal_risk, got high_risk (needs_more_information))
- Experts' comment: "low-risk, because AI is used for energy optimization" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt Deep Learning, um Überwachungsdaten auszuwerten und Empfehlungen zur Energieoptimierung abzuleiten; es führt außerdem Anpassungen automatisch aus. Ein Bezug zur Union wird angenommen, da die Beschreibung keinen unionsfremden Bezug erkennen lässt.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (needs_more_information): Bis zur Antwort auf diese Frage wird Hochrisiko über Anhang III angenommen: Ist das Rechenzentrum kritische digitale Infrastruktur, und ist das System als Sicherheitsbauteil vorgesehen, dessen Ausfall oder Fehlfunktion die Gesundheit oder Sicherheit von Personen oder Eigentum gefährden könnte?
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erzeugt Empfehlungen zur Verbesserung des Energieverbrauchs; eine gesetzliche Ausnahme für Standardbearbeitung, nicht wesentliche Veränderung oder Strafverfolgung ist nicht beschrieben. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** engine error: Annex III 2: optimising data-centre cooling energy is "optimisation-oriented" and has no direct safety function (guidelines para 181, ex 058; Recital 55). Defaulting to high is unsupported; the experts' low is right.

### Case aai-092

- Function: it_and_security
- Experts: high
- Engine: minimal_risk, decided
- Match: no
- Look first at: high_risk (expected high_risk, got minimal_risk (decided))
- Experts' comment: "The AI makes suggestions (=tasks) on how a natural person may improve their cybersecurity on the basis of an individual risk-score (influenced by individuals behaviour)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System wird als KI-gestützt und prädiktiv beschrieben und leitet aus Daten Risikoinformationen sowie einen Risiko-Score ab. Ein Bezug zur Union wird nicht ausdrücklich beschrieben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Daimler's threat-intel risk matrix scores indicators of compromise, not workers. Nothing allocates tasks on traits or evaluates employees (4(b), G-p269/277). Reading it as a personal risk score misreads the facts under any version.

### Case aai-093

- Function: it_and_security
- Experts: prohibited
- Engine: high_risk, needs_more_information, annex:III:1:a
- Match: no
- Look first at: prohibited (expected prohibited, got high_risk (needs_more_information))
- Experts' comment: "Remote Biometric Identification System for Law Enforcement (?)" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. h: Die Gesichtserkennungssoftware analysiert Live-Aufnahmen herannahender Besucherinnen und Besucher, um ihre Zutrittsberechtigung festzustellen; eine Nutzung durch oder im Auftrag einer Strafverfolgungsbehörde ist nicht beschrieben.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 1 Buchstabe a aufgeführt eingesetzt (Art. 6 Abs. 2). Keine der Bedingungen des Art. 6 Abs. 3 ist erfüllt, daher greift keine Ausnahme.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** engine error: The guideline examples track the description almost word for word. The experts' "(?)" shows their own doubt. Choose ambiguous only if you read "Person von Interesse" as a watchlist search that goes beyond access control.

### Case aai-094

- Function: it_and_security
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Not sure, if this case counts as “on behalf of an authority”, but it involves the risk for for a company to become a potential victims of criminal offences." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet Ausgaben mithilfe von maschinellem Lernen, Deep Learning, neuronalen Netzen und lernenden Verhaltensmodellen ab. Die beschriebene Nutzung findet bei einem Einzelhändler in Deutschland statt.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Network threat detection at a retailer. 6(a) concerns a natural person becoming a crime victim, assessed by or on behalf of law enforcement (G-p356(ii)). A company is not that, under 2021 either.

### Case aai-099

- Function: research_and_development
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "If the system was used by an official body (e.g. customs authority), it might be seen to assist for law enforcement. The exception in Recital 38 (AIA Apr. 2021) might not apply as the use case goes beyond supporting administrative proceedings." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System ausschließlich für die wissenschaftliche Forschung und Entwicklung entwickelt und in Betrieb genommen, ohne andere Nutzung oder Angebot?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erzeugt Formeln für potenzielle neue Designerdrogen als synthetische Inhalte; eine Ausnahme ist nicht ersichtlich. Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** outdated label: both reviews: Academic generation of designer-drug structures. No Annex III 6 use case covers substance prediction (all are person-focused, G-p371, G-ex232), and it is research (Art. 2(6)). In 2021 there was no research exclusion, but no 6 item fit either.

### Case aai-105

- Function: accounting_and_finance
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI System makes a prediction about the future payment behaviour of natural persons (creditworthiness), but unclear, if it is High-Risk, as it is used by a municipality." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das Dashboard verwendet maschinelles Lernen und ein Random-Forest-Modell, um aus Daten Vorhersagen über das künftige Zahlungsverhalten abzuleiten. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System wertet das bisherige Zahlungsverhalten einzelner Schuldner:innen aus und sagt ihr künftiges Zahlungsverhalten für die Bewertung kommunaler Forderungen voraus; eine Schlechterstellung in einem sachfremden Kontext oder eine ungerechtfertigte beziehungsweise unverhältnismäßige Behandlung ist nicht beschrieben.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: Individual-level scores are explicitly produced, but the purpose is portfolio valuation. The engine decided minimal_risk with "Es wurde keine Verwendung nach Anhang III gefunden" and never weighed 5(b). The experts' "unclear" fits. Choose engine error if you take the plain text of 5(b) as decisive.

### Case aai-106

- Function: accounting_and_finance
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Unclear, if a risk assessment for tax purposes falls under "on behalf of law enforcement authorities" and an incorrect tax declaration counts as an offence" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. GRAPA wird als KI-Tool bezeichnet; nichts in der Beschreibung deutet darauf hin, dass es nur festgelegte Regeln ausführt. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Deloitte's audit risk-strategy assistant. Statutory auditors are not law enforcement or acting on their behalf (G-p81, G-p341), and it assesses companies' books, not persons' offending. The 2021 Recital 38 excluded even tax authorities' administrative work.

### Case aai-107

- Function: accounting_and_finance
- Experts: high
- Engine: minimal_risk, decided
- Match: no
- Look first at: high_risk (expected high_risk, got minimal_risk (decided))
- Experts' comment: "High Risk, as the System is intended to assess the risk of a natural person for offending against anti-money laundering law." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt maschinelles Lernen, um Transaktionsdaten zu analysieren und verdächtige Fälle zu erkennen. Es wird angenommen, dass das System in der EU eingesetzt oder dort auf den Markt gebracht wird beziehungsweise seine Ergebnisse dort verwendet werden.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Bank AML transaction monitoring. A firm meeting its own AML duty acts "on its own behalf", so it is not under 6 (G-p81 example), and AML is outside 5(b) unless linked to credit scoring (G-p309). The 2021 6(a) required use "by" law enforcement, and a bank is not "entrusted … with public powers" (Art. 3(45)(b)).

### Case aai-108

- Function: accounting_and_finance
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "The AI system supports a financial institution in implementing legal requirements to prevent money laundering. It is unclear whether the detection of a possible criminal act should be understood here as "on behalf" of a Law enforcement authority" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System erkennt Muster und Verbindungen, clustert und klassifiziert Daten und passt sich mit der Zeit an; es leitet damit Ausgaben aus Eingaben ab. Ein EU-Bezug ist nicht beschrieben; mangels gegenteiliger Hinweise wird ein EU-Bezug angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System erstellt einen KI-Score zur Unterscheidung von Kund:innen; ob es dabei natürliche Personen über einen Zeitraum anhand ihres sozialen Verhaltens oder persönlicher Eigenschaften bewertet, ist offen. Die Bewertung dient der Betrugserkennung im Transaktionskontext und es gibt keinen Hinweis auf eine Schlechterstellung in einem anderen Kontext oder auf eine ungerechtfertigte beziehungsweise unverhältnismäßige Behandlung. Geprüft: Art. 5 Abs. 1 Buchst. d: Das System identifiziert verdächtige Transaktionen für Geldwäschebekämpfung und Betrugserkennung; ob sein Kund:innen-Score das Risiko bewertet, dass eine natürliche Person eine Straftat begeht, ist nicht angegeben. Es nutzt Transaktionsmuster und -verbindungen, und menschliche Compliance-Beauftragte überprüfen markierte Transaktionen; ob diese Prüfung bereits auf objektiven, überprüfbaren Tatsachen beruht, die unmittelbar mit einer kriminellen Aktivität zusammenhängen, bleibt offen.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** outdated label: both reviews: Fraugster e-commerce fraud rules for a retailer. Fraud detection is excluded from 5(b) (G-p306–308), and private fraud or AML compliance is not "on behalf of" law enforcement (G-p81). In 2023 the obliged-entity question under the Art. 3(45)(b)-type wording was arguably open.

### Case aai-109

- Function: accounting_and_finance
- Experts: unclear
- Engine: high_risk, decided, annex:III:4:b
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got high_risk (decided))
- Experts' comment: "The AI system supports the company in complying with financial regulations. A breach of these regulations may lead to a criminal offense. It is unclear whether the detection of a possible criminal offense should be understood here as "on behalf" of an enforcing authority, because companies are legally obliged to do so." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt Computer Vision und NLP zur Analyse und Klassifizierung von Belegen und leitet daraus Kategorien, Genehmigungen und Anomalieerkennungen ab. Es wird angenommen, dass das System in der EU eingesetzt wird oder seine Ergebnisse dort verwendet werden.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: Both readings rest on the same text. The engine's *decided* high overstates the certainty.

### Case aai-110

- Function: accounting_and_finance
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:III:5:b
- Match: counted separately
- Experts' comment: "Unclear, as the evaluation of payment behaviour (by a retail company) may count as evaluation of creditworthiness of natural persons." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System lernt aus Daten und leitet daraus Vorhersagen und Aktionen ab; es ist daher ein KI-System im Sinne von Artikel 3 Absatz 1. Es wird angenommen, dass das System in der EU eingesetzt wird.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System bewertet Kunden anhand ihres Zahlungsverhaltens und ihrer Zahlungsausfallwahrscheinlichkeit über einen Zeitraum; der Score dient der Auswahl von Kreditlimits und Zahlungsbedingungen im selben Forderungs- und Zahlungskontext.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 5 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 1, Art. 50 Abs. 2. Das System kommuniziert unmittelbar mit Kunden per E-Mail, SMS oder Brief; in diesem kundenbezogenen Kontext ist seine KI-Natur nicht offensichtlich. Die Beschreibung sagt nicht, ob das System die Texte der Kundenmitteilungen selbst erzeugt oder lediglich deren Versand und Zeitpunkt verwaltet. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): collectAI learns "für einen Ausfall typisches Kundenverhalten" from payment data. That is an assessment of "willingness to … pay for the services provided" (G-p296). Whether it counts as 5(b) depends on use for essential services (G-p301/305: the provider must show non-essential use) and on whether dunning timing is…

### Case aai-112

- Function: accounting_and_finance
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Fraud detection is required by law, and it is about assessing the risk of a natural person to commit an offence, but unclear if the use of such as System by a company is considered “on behalf of a law enforcement authority” because the company is legally obliged to detect fraud." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die beschriebenen Systeme leiten aus Daten Muster und Verbindungen ab; das Betrugserkennungssystem passt sich zudem mit der Zeit an. Es wird angenommen, dass mindestens eines der Systeme in der EU eingesetzt wird oder seine Ausgaben dort verwendet werden.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: A travel platform's promo-abuse detection. It is voluntary commercial fraud prevention (no legal duty), so not "on behalf of" law enforcement (G-p81), and the 5(b) fraud exception applies anyway. The 2021 text required use "by" law enforcement.

### Case aai-114

- Function: accounting_and_finance
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:III:4:b
- Match: counted separately
- Experts' comment: "Evaluating the compliance of expense requests may count as assessing the risk of someone to commit an offence" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet aus Belegbildern und Text Kostenkategorien, verdächtiges Verhalten und mögliche Genehmigungen ab. Ein Einsatz oder eine Bereitstellung in der EU ist angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu. Geprüft: Art. 5 Abs. 1 Buchst. c: Das System bewertet das Erstattungsverhalten von Mitarbeiter:innen anhand von Spesenbelegen und erkennt verdächtige Muster im Rahmen einer spezifischen Prüfung von Spesenabrechnungen.
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: for the same reasons as aai-109 (same generic text). The employee-compliance framing makes high slightly stronger here. The case is counted separately (needs_more_information comes from the role step).

### Case aai-116

- Function: marketing_sales
- Experts: unclear
- Engine: prohibited, needs_more_information, annex:III:4:b
- Match: counted separately
- Experts' comment: "Onboarding is about learning a new job, and the AI is evaluating a persons progress in onboarding and suggests improvements" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet aus Gesprächseingaben Muster, Vorhersagen und Vorschläge ab und ist daher ein KI-System. Ein Unionsbezug ist nicht beschrieben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (needs_more_information): Das System überwacht Verkaufsgespräche von Vertriebsmitarbeiter:innen am Arbeitsplatz, aber die Beschreibung lässt offen, ob es aus biometrischen Daten Emotionen oder Absichten ableitet. Bis zur Antwort auf diese Frage wird ein Verbot nach Art. 5 Abs. 1 Buchst. f angenommen: Erkennt das System Gefühle oder Absichten von Menschen, etwa Stress, Frust oder Langeweile, zum Beispiel aus Gesicht, Stimme, Tippverhalten oder anderen Körpersignalen?
- Engine, high_risk (decided): Hochrisiko: Das System wird wie in Anhang III Nummer 4 Buchstabe b aufgeführt eingesetzt (Art. 6 Abs. 2). Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach Art. 6 Abs. 3 nicht greifen.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Ob die Echtzeit-Tipps als synthetischer Text ausgegeben werden, bleibt offen; eine Punktzahl oder Analyse allein ist kein synthetischer Inhalt. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** engine error: Annex III 4(b): Gong records, transcribes and scores reps' sales calls for managers, so the class is high. Art. 5(1)(f) needs emotion inference from biometric data, and only speech-to-text plus NLP is described, so the prohibition default is unsupported.

### Case aai-119

- Function: marketing_sales
- Experts: low
- Engine: prohibited, needs_more_information
- Match: no
- Look first at: prohibited (expected minimal_risk, got prohibited (needs_more_information))
- Experts' comment: none
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System nutzt maschinelles Lernen, um aus Verkaufsdaten und externen Faktoren den besten Preis zu ermitteln; es ist damit ein KI-System. Der Einsatz erfolgt vermutlich in der EU.
- Engine, prohibited (needs_more_information): Das System kann Preise anhand des Kaufverhaltens einzelner Kund:innen variieren; ob dies zu ungerechtfertigter oder unverhältnismäßiger Schlechterstellung führt, ist nicht angegeben. Bis zur Antwort auf diese Frage wird ein Verbot nach Art. 5 Abs. 1 Buchst. c angenommen: Führt die Bewertung zu einer schlechteren Behandlung, die ungerechtfertigt ist oder in keinem Verhältnis zu dem Verhalten steht, auf dem sie beruht?
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** engine error: Art. 5(1)(c): demand-based markdown pricing (Bonprix) is not social scoring with detriment in an unrelated context or out of proportion (prohibited-practices guidelines para 177). The experts' low is right.

## Annex I disagreements (12)

### Case aai-011

- Function: production_and_manufacturing
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Predictive maintenance of machinery, which is in Annex II" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System ausschließlich für die wissenschaftliche Forschung und Entwicklung entwickelt und in Betrieb genommen, ohne andere Nutzung oder Angebot?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Condition monitoring of pressure and temperature signals for preventive maintenance. AI-p37 lists detecting "a need for maintenance … where failure … may lead to physical harm" and "abnormal system behaviour" as safety functions, and AI-p22 says add-ons count. The class turns on whether the monitored parts are…

### Case aai-016

- Function: production_and_manufacturing
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:III:2
- Match: counted separately
- Experts' comment: "The AI is managing the energy consumption of a machine, which likely falls into the machinery Directive (annex II). It is unclear whether the energy supply is a safety critical component." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet aus Anlagendaten Vorhersagen und Strategien ab und optimiert seine Parameter mittels Deep Learning und Reinforcement Learning. Ein Bezug zur Union ist nicht angegeben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (needs_more_information): Bis zur Antwort auf diese Frage wird Hochrisiko über Anhang III angenommen: Könnte ein Ausfall oder eine Fehlfunktion des KI-Systems Personen oder Eigentum gefährden, oder erfüllt das System bestimmungsgemäß eine Sicherheitsfunktion, die solche Risiken verhindert oder mindert?
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** engine error: Annex III 2 "supply of gas" means natural-gas entities identified under CER (guidelines para 199-200), and Linde's O2/N2 plant energy optimiser is optimisation-oriented (para 181). The high default is unsupported; the class should be minimal.

### Case aai-017

- Function: production_and_manufacturing
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "Unclear, if the maintenance of a machine is considered safety critical, because it is no component itself, but a failure of maintenance may be safety critical." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Systeme leiten aus Eingaben Vorhersagen und Empfehlungen ab; sie werden mit Deep Learning, Reinforcement Learning beziehungsweise maschinellem Lernen umgesetzt. Es wird angenommen, dass die Systeme in der EU eingesetzt werden oder ihre Ergebnisse dort verwendet werden.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Porsche's acoustic system predicts wear on robots, hydraulic lifts and screwdrivers ("Schrauben, die sich lösen"). That matches AI-p37 (detecting worn safety-related parts), and use at its own plant counts as "putting into service". The Linde plant optimiser could be a failure-based safety component (AI-ex001). Both…

### Case aai-024

- Function: production_and_manufacturing
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The use case is about AI generated design of a seat belt for cars, which are (presumably) safety components. Cars need to undergo 3rd party assessments. However, the AI is not part of the car." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die generative Konstruktionssoftware untersucht Lösungen, erzeugt Designalternativen und lernt aus Wiederholungen; sie leitet damit Ausgaben aus Eingaben ab. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erzeugt Designalternativen für die Produktentwicklung; ob seine Ausgaben Audio-, Bild-, Video- oder Textinhalte sind, ist nicht angegeben. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: Generative design of a seat bracket. The AI is a design tool, not "part of a product" (Art. 3(14), AI-p31). The experts' own note concedes "the AI is not part of the car". 2021 Art. 6(1) had the same safety-component condition.

### Case aai-077

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: high_risk, needs_more_information, annex:I:B:20
- Match: counted separately
- Experts' comment: "The AI is predicting potential failures of critical aircraft components eg. turbines, and civil aviation is listed in Annex II" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die Anwendung leitet aus erlernten Mustern historischer Warnungen Empfehlungen und Vertrauensniveaus ab und ist damit ein KI-System nach Artikel 3 Absatz 1. Ein Bezug zur Union wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (needs_more_information): Bis zur Antwort auf diese Frage wird Hochrisiko über Anhang I angenommen: Erfüllt das KI-System eine Sicherheitsfunktion für das Produkt, das unter Verordnung (EU) 2018/1139 zur Festlegung gemeinsamer Vorschriften für die Zivilluftfahrt und zur Errichtung einer Agentur der Europäischen Union für Flugsicherheit fällt, oder könnte sein Ausfall oder seine Störung die Gesundheit oder Sicherheit von Menschen gefährden?
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** engine error: Annex I B:20 covers Reg. 2018/1139 only for unmanned aircraft. GE's ground-side alert-triage tool for airline engines is neither an unmanned aircraft nor a part of one, so defaulting to high is unsupported.

### Case aai-081

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Unclear what the AI does, but drones are listed in Annex II, Section B, item 8" (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wie erzeugt das System seine Ergebnisse: Wurde es mit Daten trainiert oder leitet es sie auf andere Weise ab, oder wendet es nur von Menschen festgelegte Regeln oder Berechnungen an?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Autonomous inventory drones flying in high-rack aisles near workers. Whether the AI does navigation or collision avoidance (a safety function, AI-p37/39) or only barcode reading isn't stated (the experts flagged the same gap). Indoor drones' coverage by Reg. 2018/1139 and the third-party route also need product facts.

### Case aai-082

- Function: logistics_and_supply_chains
- Experts: unclear
- Engine: minimal_risk, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got minimal_risk (decided))
- Experts' comment: "The rail system falls under Annex 2 Section B and the purpose of the AI system is to identify and report damage to wagons. As undetected damage can be safety critical, it is unclear whether the AI system is a safety component in the sense of the AI Regulation." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Das System leitet mithilfe trainierter KI-Bildklassifikatoren aus Bildern Schadensarten und Reparaturmaßnahmen ab. Ein Unionsbezug ist nicht angegeben; mangels gegenteiliger Hinweise wird er angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** ambiguous: The experts' "unclear" fits. The engine decided minimal_risk without addressing the maintenance-as-safety-function point in the Annex I guidelines.

### Case aai-089

- Function: it_and_security
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI is protecting the cyber security and correct functioning of devices in the health sector e.g. insuline pumps, which fall under Annex II, but it is unclear if the AI System counts as safety critical compoment." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach Art. 2 greift. Die KI lernt Netzwerkverkehrsmuster und leitet daraus Empfehlungen für Workload-Gruppierungen und Sicherheitsrichtlinien ab. Ein Unionsbezug wird mangels gegenteiliger Angaben angenommen.
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Die Systeme klassifizieren Bedrohungen und empfehlen Gruppierungen oder Richtlinien; ob sie diese Ergebnisse als strukturierte Analyse oder als verfassten Text ausgeben, bleibt offen. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** ambiguous: experts' label defensible on one reading (advocate review): Endpoint management for 80k corporate devices and IoT wearables at a pharma firm. Under Art. 6(1), cybersecurity components can be safety components where failure endangers health (AI-p38, footnote: the Recital 55 carve-out is limited to critical infrastructure), and add-ons count (AI-p22). The fact: whether the…

### Case aai-096

- Function: research_and_development
- Experts: unclear
- Engine: limited_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI System is put into usage, but not placed on the market as a product. Choosing the "right" molecule seems critical for developing a medicine." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System ausschließlich für die wissenschaftliche Forschung und Entwicklung entwickelt und in Betrieb genommen, ohne andere Nutzung oder Angebot?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (needs_more_information): Transparenzpflichten bestehen nach Art. 50 Abs. 2. Das System erzeugt Molekülkandidaten, aber die Beschreibung sagt nicht, ob seine Ausgaben Audio-, Bild-, Video- oder Textinhalte sind. Bis zur Antwort auf diese Frage wird Art. 50 Abs. 2 angenommen: Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen erstellte Inhalte aus oder spielt sie ab? Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen seine Ausgaben bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.

**Verdict:** label error: both reviews: Molecule generation for drug discovery. Medicinal-product law is not in Annex I (it lists MDR and IVDR only), so there is no product route. The 2021 Annex II was the same, and Art. 2(6) now adds an R&D exclusion.

### Case aai-100

- Function: research_and_development
- Experts: unclear
- Engine: out_of_scope, decided
- Match: no
- Look first at: uncertain status (appliedAI unclear) (expected none, got out_of_scope (decided))
- Experts' comment: "The autonomous robot is likely a machine under Annex II, Section A. As it operates with a high level of autonomy and (from what it sounds) in the same space as humans, a failure of the system may cause damage to health, safety or property." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (decided): Nicht anwendbar: Die KI-Verordnung gilt nicht. Art. 2 Abs. 6: Es wird eigens für den alleinigen Zweck der wissenschaftlichen Forschung und Entwicklung entwickelt und in Betrieb genommen.

**Verdict:** outdated label: both reviews: University of Liverpool's autonomous lab robot was developed and used solely for the scientists' research, so Art. 2(6) and Recital 25 exclude it. Absent that, the machinery and safety question was genuinely open (navigates among humans, AI-p37). The research exclusion is new since 2021.

### Case aai-101

- Function: research_and_development
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "Electric vehicles are machines in the sense of the Machinery Directive (Directive 2006/42/EC), which is listed in Annex 2 Section A of the AI Regulation for risk classification. The seat belt mount could be considered a safety-critical component of the vehicle because the seat belt is attached to it. However, the AI system is only used to develop the bracket, but it is not part of the vehicle." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wie erzeugt das System seine Ergebnisse: Wurde es mit Daten trainiert oder leitet es sie auf andere Weise ab, oder wendet es nur von Menschen festgelegte Regeln oder Berechnungen an?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Same GM generative-design bracket as aai-024. It is a design tool, not a component (Art. 3(14), AI-p31). Vehicles are type-approval products, not Machinery Directive products as the note claims.

### Case aai-103

- Function: research_and_development
- Experts: unclear
- Engine: minimal_risk, needs_more_information
- Match: counted separately
- Experts' comment: "The AI System is put into usage, but not placed on the market as a product. Choosing the "right" molecule seems critical for developing a medicine." (appliedAI Institute for Europe gGmbH, CC BY 4.0)
- Engine, scope (needs_more_information): Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden seine Ergebnisse in der EU verwendet?
- Engine, prohibited (decided): Keine verbotene Praxis nach Art. 5 trifft zu.
- Engine, high_risk (decided): Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine Konformitätsbewertung durch Dritte durchlaufen muss.
- Engine, transparency (decided): Keine Transparenzpflicht nach Art. 50 trifft zu.

**Verdict:** label error: both reviews: Cambridge reaction-prediction research model. It is no product or safety component under any Annex I act, under 2021 too, and Art. 2(6) now excludes it outright.
