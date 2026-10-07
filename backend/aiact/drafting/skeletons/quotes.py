"""The requirements the skeletons quote, word for word from the consolidated AI Act of 27 July
2026 (CELEX 02024R1689-20260727): the English text and the official German one, by provision id,
exactly as `get_provision` returns them. A test checks every quote against the corpus built from
`data/parsed/`, so a changed corpus text fails the build rather than a quote drifting. Never
edit a quote by hand to reword it.
"""

from collections.abc import Mapping

from aiact.drafting.templates import DE, EN, Requirement, Texts


def requirement(provision_id: str) -> Requirement:
    """The requirement of `provision_id`, quoted from `QUOTES`."""
    return Requirement(provision_id, QUOTES[provision_id])


QUOTES: Mapping[str, Texts] = {
    "annex:IV:1": {
        EN: (
            "A general description of the AI system including:\n(a) its intended purpose, the "
            "name of the provider and the version of the system reflecting its relation to "
            "previous versions;\n(b) how the AI system interacts with, or can be used to "
            "interact with, hardware or software, including with other AI systems, that are "
            "not part of the AI system itself, where applicable;\n(c) the versions of relevant "
            "software or firmware, and any requirements related to version updates;\n(d) the "
            "description of all the forms in which the AI system is placed on the market or "
            "put into service, such as software packages embedded into hardware, downloads, or "
            "APIs;\n(e) the description of the hardware on which the AI system is intended to "
            "run;\n(f) where the AI system is a component of products, photographs or "
            "illustrations showing external features, the marking and internal layout of those "
            "products;\n(g) a basic description of the user-interface provided to the "
            "deployer;\n(h) instructions for use for the deployer, and a basic description of "
            "the user-interface provided to the deployer, where applicable;"
        ),
        DE: (
            "Allgemeine Beschreibung des KI-Systems, darunter\na) Zweckbestimmung, Name des "
            "Anbieters und Version des Systems mit Angaben dazu, in welcher Beziehung sie zu "
            "vorherigen Versionen steht;\nb) gegebenenfalls Interaktion oder Verwendung des "
            "KI-Systems mit Hardware oder Software, einschließlich anderer KI-Systeme, die "
            "nicht Teil des KI-Systems selbst sind;\nc) Versionen der betreffenden Software "
            "oder Firmware und etwaige Anforderungen in Bezug auf Aktualisierungen der "
            "Versionen;\nd) Beschreibung aller Formen, in denen das KI-System in Verkehr "
            "gebracht oder in Betrieb genommen wird, zum Beispiel in Hardware eingebettete "
            "Softwarepakete, Herunterladen oder API;\ne) Beschreibung der Hardware, auf der "
            "das KI-System betrieben werden soll;\nf) falls das KI-System Bestandteil von "
            "Produkten ist: Fotografien oder Abbildungen, die äußere Merkmale, die "
            "Kennzeichnungen und den inneren Aufbau dieser Produkte zeigen;\ng) eine "
            "grundlegende Beschreibung der Benutzerschnittstelle, die dem Betreiber zur "
            "Verfügung gestellt wird;\nh) Betriebsanleitungen für den Betreiber und "
            "gegebenenfalls eine grundlegende Beschreibung der dem Betreiber zur Verfügung "
            "gestellten Benutzerschnittstelle;"
        ),
    },
    "annex:IV:2": {
        EN: (
            "A detailed description of the elements of the AI system and of the process for "
            "its development, including:\n(a) the methods and steps performed for the "
            "development of the AI system, including, where relevant, recourse to pre-trained "
            "systems or tools provided by third parties and how those were used, integrated or "
            "modified by the provider;\n(b) the design specifications of the system, namely "
            "the general logic of the AI system and of the algorithms; the key design choices "
            "including the rationale and assumptions made, including with regard to persons or "
            "groups of persons in respect of who, the system is intended to be used; the main "
            "classification choices; what the system is designed to optimise for, and the "
            "relevance of the different parameters; the description of the expected output and "
            "output quality of the system; the decisions about any possible trade-off made "
            "regarding the technical solutions adopted to comply with the requirements set out "
            "in Chapter III, Section 2;\n(c) the description of the system architecture "
            "explaining how software components build on or feed into each other and integrate "
            "into the overall processing; the computational resources used to develop, train, "
            "test and validate the AI system;\n(d) where relevant, the data requirements in "
            "terms of datasheets describing the training methodologies and techniques and the "
            "training data sets used, including a general description of these data sets, "
            "information about their provenance, scope and main characteristics; how the data "
            "was obtained and selected; labelling procedures (e.g. for supervised learning), "
            "data cleaning methodologies (e.g. outliers detection);\n(e) assessment of the "
            "human oversight measures needed in accordance with Article 14, including an "
            "assessment of the technical measures needed to facilitate the interpretation of "
            "the outputs of AI systems by the deployers, in accordance with Article 13(3), "
            "point (d);\n(f) where applicable, a detailed description of pre-determined "
            "changes to the AI system and its performance, together with all the relevant "
            "information related to the technical solutions adopted to ensure continuous "
            "compliance of the AI system with the relevant requirements set out in Chapter "
            "III, Section 2;\n(g) the validation and testing procedures used, including "
            "information about the validation and testing data used and their main "
            "characteristics; metrics used to measure accuracy, robustness and compliance with "
            "other relevant requirements set out in Chapter III, Section 2, as well as "
            "potentially discriminatory impacts; test logs and all test reports dated and "
            "signed by the responsible persons, including with regard to pre-determined "
            "changes as referred to under point (f);\n(h) cybersecurity measures put in place;"
        ),
        DE: (
            "Detaillierte Beschreibung der Bestandteile des KI-Systems und seines "
            "Entwicklungsprozesses, darunter\na) Methoden und Schritte zur Entwicklung des "
            "KI-Systems, gegebenenfalls einschließlich des Einsatzes von durch Dritte "
            "bereitgestellten vortrainierten Systemen oder Instrumenten, und wie diese vom "
            "Anbieter verwendet, integriert oder verändert wurden;\nb) Entwurfsspezifikationen "
            "des Systems, insbesondere die allgemeine Logik des KI-Systems und der "
            "Algorithmen; die wichtigsten Entwurfsentscheidungen mit den Gründen und "
            "getroffenen Annahmen, einschließlich in Bezug auf Personen oder Personengruppen, "
            "bezüglich deren das System angewandt werden soll; hauptsächliche "
            "Einstufungsentscheidungen; was das System optimieren soll und welche Bedeutung "
            "den verschiedenen Parametern dabei zukommt; Beschreibung der erwarteten Ausgabe "
            "des Systems und der erwarteten Qualität dieser Ausgabe; die über mögliche "
            "Kompromisse in Bezug auf die technischen Lösungen, mit denen die in Kapitel III "
            "Abschnitt 2 festgelegten Anforderungen erfüllt werden sollen, getroffenen "
            "Entscheidungen;\nc) Beschreibung der Systemarchitektur, aus der hervorgeht, wie "
            "Softwarekomponenten aufeinander aufbauen oder einander zuarbeiten und in die "
            "Gesamtverarbeitung integriert sind; zum Entwickeln, Trainieren, Testen und "
            "Validieren des KI-Systems verwendete Rechenressourcen;\nd) gegebenenfalls "
            "Datenanforderungen in Form von Datenblättern, in denen die Trainingsmethoden und "
            "-techniken und die verwendeten Trainingsdatensätze beschrieben werden, "
            "einschließlich einer allgemeinen Beschreibung dieser Datensätze sowie "
            "Informationen zu deren Herkunft, Umfang und Hauptmerkmalen; Angaben zur "
            "Beschaffung und Auswahl der Daten; Kennzeichnungsverfahren (zum Beispiel für "
            "überwachtes Lernen) und Datenbereinigungsmethoden (zum Beispiel Erkennung von "
            "Ausreißern);\ne) Bewertung der nach Artikel 14 erforderlichen Maßnahmen der "
            "menschlichen Aufsicht, mit einer Bewertung der technischen Maßnahmen, die "
            "erforderlich sind, um den Betreibern gemäß Artikel 13 Absatz 3 Buchstabe d die "
            "Interpretation der Ausgaben von KI-Systemen zu erleichtern;\nf) gegebenenfalls "
            "detaillierte Beschreibung der vorab bestimmten Änderungen an dem KI-System und "
            "seiner Leistung mit allen einschlägigen Informationen zu den technischen "
            "Lösungen, mit denen sichergestellt wird, dass das KI-System die einschlägigen in "
            "Kapitel III Abschnitt 2 festgelegten Anforderungen weiterhin dauerhaft "
            "erfüllt;\ng) verwendete Validierungs- und Testverfahren, mit Informationen zu den "
            "verwendeten Validierungs- und Testdaten und deren Hauptmerkmalen; Parameter, die "
            "zur Messung der Genauigkeit, Robustheit und der Erfüllung anderer einschlägiger "
            "Anforderungen nach Kapitel III Abschnitt 2 sowie potenziell diskriminierender "
            "Auswirkungen verwendet werden; Testprotokolle und alle von den verantwortlichen "
            "Personen datierten und unterzeichneten Testberichte, auch in Bezug auf die unter "
            "Buchstabe f genannten vorab bestimmten Änderungen;\nh) ergriffene "
            "Cybersicherheitsmaßnahmen;"
        ),
    },
    "annex:IV:3": {
        EN: (
            "Detailed information about the monitoring, functioning and control of the AI "
            "system, in particular with regard to: its capabilities and limitations in "
            "performance, including the degrees of accuracy for specific persons or groups of "
            "persons on which the system is intended to be used and the overall expected level "
            "of accuracy in relation to its intended purpose; the foreseeable unintended "
            "outcomes and sources of risks to health and safety, fundamental rights and "
            "discrimination in view of the intended purpose of the AI system; the human "
            "oversight measures needed in accordance with Article 14, including the technical "
            "measures put in place to facilitate the interpretation of the outputs of AI "
            "systems by the deployers; specifications on input data, as appropriate;"
        ),
        DE: (
            "Detaillierte Informationen über die Überwachung, Funktionsweise und Kontrolle des "
            "KI-Systems, insbesondere in Bezug auf Folgendes: die Fähigkeiten und "
            "Leistungsgrenzen des Systems, einschließlich der Genauigkeitsgrade bei bestimmten "
            "Personen oder Personengruppen, auf die es bestimmungsgemäß angewandt werden soll, "
            "sowie des in Bezug auf seine Zweckbestimmung insgesamt erwarteten Maßes an "
            "Genauigkeit; angesichts der Zweckbestimmung des KI-Systems vorhersehbare "
            "unbeabsichtigte Ergebnisse und Quellen von Risiken in Bezug auf Gesundheit und "
            "Sicherheit sowie Grundrechte und Diskriminierung; die nach Artikel 14 "
            "erforderlichen Maßnahmen der menschlichen Aufsicht, einschließlich der "
            "technischen Maßnahmen, die getroffen wurden, um den Betreibern die Interpretation "
            "der Ausgaben von KI-Systemen zu erleichtern; gegebenenfalls Spezifikationen zu "
            "Eingabedaten;"
        ),
    },
    "annex:IV:4": {
        EN: (
            "A description of the appropriateness of the performance metrics for the specific "
            "AI system;"
        ),
        DE: "Darlegungen zur Eignung der Leistungskennzahlen für das spezifische KI-System;",
    },
    "annex:IV:5": {
        EN: "A detailed description of the risk management system in accordance with Article 9;",
        DE: "Detaillierte Beschreibung des Risikomanagementsystems gemäß Artikel 9;",
    },
    "annex:IV:6": {
        EN: (
            "A description of relevant changes made by the provider to the system through its "
            "lifecycle;"
        ),
        DE: (
            "Beschreibung einschlägiger Änderungen, die der Anbieter während des Lebenszyklus "
            "an dem System vorgenommen hat;"
        ),
    },
    "annex:IV:7": {
        EN: (
            "A list of the harmonised standards applied in full or in part the references of "
            "which have been published in the Official Journal of the European Union; where no "
            "such harmonised standards have been applied, a detailed description of the "
            "solutions adopted to meet the requirements set out in Chapter III, Section 2, "
            "including a list of other relevant standards and technical specifications applied;"
        ),
        DE: (
            "Aufstellung der vollständig oder teilweise angewandten harmonisierten Normen, "
            "deren Fundstellen im Amtsblatt der Europäischen Union veröffentlicht wurden; "
            "falls keine solchen harmonisierten Normen angewandt wurden, eine detaillierte "
            "Beschreibung der Lösungen, mit denen die in Kapitel III Abschnitt 2 festgelegten "
            "Anforderungen erfüllt werden sollen, mit einer Aufstellung anderer angewandter "
            "einschlägiger Normen und technischer Spezifikationen;"
        ),
    },
    "annex:IV:8": {
        EN: "A copy of the EU declaration of conformity referred to in Article 47;",
        DE: "Kopie der EU-Konformitätserklärung gemäß Artikel 47;",
    },
    "annex:IV:9": {
        EN: (
            "A detailed description of the system in place to evaluate the AI system "
            "performance in the post-market phase in accordance with Article 72, including the "
            "post-market monitoring plan referred to in Article 72(3)."
        ),
        DE: (
            "Detaillierte Beschreibung des Systems zur Bewertung der Leistung des KI-Systems "
            "in der Phase nach dem Inverkehrbringen gemäß Artikel 72, einschließlich des in "
            "Artikel 72 Absatz 3 genannten Plans für die Beobachtung nach dem Inverkehrbringen"
        ),
    },
    "art:9:1": {
        EN: (
            "A risk management system shall be established, implemented, documented and "
            "maintained in relation to high-risk AI systems."
        ),
        DE: (
            "Für Hochrisiko-KI-Systeme wird ein Risikomanagementsystem eingerichtet, "
            "angewandt, dokumentiert und aufrechterhalten."
        ),
    },
    "art:9:2:a": {
        EN: (
            "the identification and analysis of the known and the reasonably foreseeable risks "
            "that the high-risk AI system can pose to health, safety or fundamental rights "
            "when the high-risk AI system is used in accordance with its intended purpose;"
        ),
        DE: (
            "die Ermittlung und Analyse der bekannten und vernünftigerweise vorhersehbaren "
            "Risiken, die vom Hochrisiko-KI-System für die Gesundheit, Sicherheit oder "
            "Grundrechte ausgehen können, wenn es entsprechend seiner Zweckbestimmung "
            "verwendet wird;"
        ),
    },
    "art:9:2:b": {
        EN: (
            "the estimation and evaluation of the risks that may emerge when the high-risk AI "
            "system is used in accordance with its intended purpose, and under conditions of "
            "reasonably foreseeable misuse;"
        ),
        DE: (
            "die Abschätzung und Bewertung der Risiken, die entstehen können, wenn das "
            "Hochrisiko-KI-System entsprechend seiner Zweckbestimmung oder im Rahmen einer "
            "vernünftigerweise vorhersehbaren Fehlanwendung verwendet wird;"
        ),
    },
    "art:9:2:c": {
        EN: (
            "the evaluation of other risks possibly arising, based on the analysis of data "
            "gathered from the post-market monitoring system referred to in Article 72;"
        ),
        DE: (
            "die Bewertung anderer möglicherweise auftretender Risiken auf der Grundlage der "
            "Auswertung der Daten aus dem in Artikel 72 genannten System zur Beobachtung nach "
            "dem Inverkehrbringen;"
        ),
    },
    "art:9:2:d": {
        EN: (
            "the adoption of appropriate and targeted risk management measures designed to "
            "address the risks identified pursuant to point (a)."
        ),
        DE: (
            "die Ergreifung geeigneter und gezielter Risikomanagementmaßnahmen zur Bewältigung "
            "der gemäß Buchstabe a ermittelten Risiken."
        ),
    },
    "art:9:5": {
        EN: (
            "The risk management measures referred to in paragraph 2, point (d), shall be such "
            "that the relevant residual risk associated with each hazard, as well as the "
            "overall residual risk of the high-risk AI systems is judged to be acceptable.\nIn "
            "identifying the most appropriate risk management measures, the following shall be "
            "ensured:\n(a) elimination or reduction of risks identified and evaluated pursuant "
            "to paragraph 2 in as far as technically feasible through adequate design and "
            "development of the high-risk AI system;\n(b) where appropriate, implementation of "
            "adequate mitigation and control measures addressing risks that cannot be "
            "eliminated;\n(c) provision of information required pursuant to Article 13 and, "
            "where appropriate, training to deployers.\nWith a view to eliminating or reducing "
            "risks related to the use of the high-risk AI system, due consideration shall be "
            "given to the technical knowledge, experience, education, the training to be "
            "expected by the deployer, and the presumable context in which the system is "
            "intended to be used."
        ),
        DE: (
            "Die in Absatz 2 Buchstabe d genannten Risikomanagementmaßnahmen werden so "
            "gestaltet, dass jedes mit einer bestimmten Gefahr verbundene relevante Restrisiko "
            "sowie das Gesamtrestrisiko der Hochrisiko-KI-Systeme als vertretbar beurteilt "
            "wird.\nBei der Festlegung der am besten geeigneten Risikomanagementmaßnahmen ist "
            "Folgendes sicherzustellen:\na) soweit technisch möglich, Beseitigung oder "
            "Verringerung der gemäß Absatz 2 ermittelten und bewerteten Risiken durch eine "
            "geeignete Konzeption und Entwicklung des Hochrisiko-KI-Systems;\nb) "
            "gegebenenfalls Anwendung angemessener Minderungs- und Kontrollmaßnahmen zur "
            "Bewältigung nicht auszuschließender Risiken;\nc) Bereitstellung der gemäß Artikel "
            "13 erforderlichen Informationen und gegebenenfalls entsprechende Schulung der "
            "Betreiber.\nZur Beseitigung oder Verringerung der Risiken im Zusammenhang mit der "
            "Verwendung des Hochrisiko-KI-Systems werden die technischen Kenntnisse, die "
            "Erfahrungen und der Bildungsstand, die vom Betreiber erwartet werden können, "
            "sowie der voraussichtliche Kontext, in dem das System eingesetzt werden soll, "
            "gebührend berücksichtigt."
        ),
    },
    "art:9:6": {
        EN: (
            "High-risk AI systems shall be tested for the purpose of identifying the most "
            "appropriate and targeted risk management measures. Testing shall ensure that "
            "high-risk AI systems perform consistently for their intended purpose and that "
            "they are in compliance with the requirements set out in this Section."
        ),
        DE: (
            "Hochrisiko-KI-Systeme müssen getestet werden, um die am besten geeigneten "
            "gezielten Risikomanagementmaßnahmen zu ermitteln. Durch das Testen wird "
            "sichergestellt, dass Hochrisiko-KI-Systeme stets im Einklang mit ihrer "
            "Zweckbestimmung funktionieren und die Anforderungen dieses Abschnitts erfüllen."
        ),
    },
    "art:9:8": {
        EN: (
            "The testing of high-risk AI systems shall be performed, as appropriate, at any "
            "time throughout the development process, and, in any event, prior to their being "
            "placed on the market or put into service. Testing shall be carried out against "
            "prior defined metrics and probabilistic thresholds that are appropriate to the "
            "intended purpose of the high-risk AI system."
        ),
        DE: (
            "Das Testen von Hochrisiko-KI-Systemen erfolgt zu jedem geeigneten Zeitpunkt "
            "während des gesamten Entwicklungsprozesses und in jedem Fall vor ihrem "
            "Inverkehrbringen oder ihrer Inbetriebnahme. Das Testen erfolgt anhand vorab "
            "festgelegter Metriken und Wahrscheinlichkeitsschwellenwerte, die für die "
            "Zweckbestimmung des Hochrisiko-KI-Systems geeignet sind."
        ),
    },
    "art:9:9": {
        EN: (
            "When implementing the risk management system as provided for in paragraphs 1 to "
            "7, providers shall give consideration to whether in view of its intended purpose "
            "the high-risk AI system is likely to have an adverse impact on persons under the "
            "age of 18 and, as appropriate, other vulnerable groups."
        ),
        DE: (
            "Bei der Umsetzung des in den Absätzen 1 bis 7 vorgesehenen "
            "Risikomanagementsystems berücksichtigen die Anbieter, ob angesichts seiner "
            "Zweckbestimmung das Hochrisiko-KI-System wahrscheinlich nachteilige Auswirkungen "
            "auf Personen unter 18 Jahren oder gegebenenfalls andere schutzbedürftige Gruppen "
            "haben wird."
        ),
    },
    "art:17:1:a": {
        EN: (
            "a strategy for regulatory compliance, including compliance with conformity "
            "assessment procedures and procedures for the management of modifications to the "
            "high-risk AI system;"
        ),
        DE: (
            "ein Konzept zur Einhaltung der Regulierungsvorschriften, was die Einhaltung der "
            "Konformitätsbewertungsverfahren und der Verfahren für das Management von "
            "Änderungen an dem Hochrisiko-KI-System miteinschließt;"
        ),
    },
    "art:17:1:b": {
        EN: (
            "techniques, procedures and systematic actions to be used for the design, design "
            "control and design verification of the high-risk AI system;"
        ),
        DE: (
            "Techniken, Verfahren und systematische Maßnahmen für den Entwurf, die "
            "Entwurfskontrolle und die Entwurfsprüfung des Hochrisiko-KI-Systems;"
        ),
    },
    "art:17:1:c": {
        EN: (
            "techniques, procedures and systematic actions to be used for the development, "
            "quality control and quality assurance of the high-risk AI system;"
        ),
        DE: (
            "Techniken, Verfahren und systematische Maßnahmen für die Entwicklung, "
            "Qualitätskontrolle und Qualitätssicherung des Hochrisiko-KI-Systems;"
        ),
    },
    "art:17:1:d": {
        EN: (
            "examination, test and validation procedures to be carried out before, during and "
            "after the development of the high-risk AI system, and the frequency with which "
            "they have to be carried out;"
        ),
        DE: (
            "Untersuchungs-, Test- und Validierungsverfahren, die vor, während und nach der "
            "Entwicklung des Hochrisiko-KI-Systems durchzuführen sind, und die Häufigkeit der "
            "Durchführung;"
        ),
    },
    "art:17:1:e": {
        EN: (
            "technical specifications, including standards, to be applied and, where the "
            "relevant harmonised standards are not applied in full or do not cover all of the "
            "relevant requirements set out in Section 2, the means to be used to ensure that "
            "the high-risk AI system complies with those requirements;"
        ),
        DE: (
            "die technischen Spezifikationen und Normen, die anzuwenden sind und, falls die "
            "einschlägigen harmonisierten Normen nicht vollständig angewandt werden oder sie "
            "nicht alle relevanten Anforderungen gemäß Abschnitt 2 abdecken, die Mittel, mit "
            "denen gewährleistet werden soll, dass das Hochrisiko-KI-System diese "
            "Anforderungen erfüllt;"
        ),
    },
    "art:17:1:f": {
        EN: (
            "systems and procedures for data management, including data acquisition, data "
            "collection, data analysis, data labelling, data storage, data filtration, data "
            "mining, data aggregation, data retention and any other operation regarding the "
            "data that is performed before and for the purpose of the placing on the market or "
            "the putting into service of high-risk AI systems;"
        ),
        DE: (
            "Systeme und Verfahren für das Datenmanagement, einschließlich Datengewinnung, "
            "Datenerhebung, Datenanalyse, Datenkennzeichnung, Datenspeicherung, "
            "Datenfilterung, Datenauswertung, Datenaggregation, Vorratsdatenspeicherung und "
            "sonstiger Vorgänge in Bezug auf die Daten, die im Vorfeld und für die Zwecke des "
            "Inverkehrbringens oder der Inbetriebnahme von Hochrisiko-KI-Systemen durchgeführt "
            "werden;"
        ),
    },
    "art:17:1:g": {
        EN: "the risk management system referred to in Article 9;",
        DE: "das in Artikel 9 genannte Risikomanagementsystem;",
    },
    "art:17:1:h": {
        EN: (
            "the setting-up, implementation and maintenance of a post-market monitoring "
            "system, in accordance with Article 72;"
        ),
        DE: (
            "die Einrichtung, Anwendung und Aufrechterhaltung eines Systems zur Beobachtung "
            "nach dem Inverkehrbringen gemäß Artikel 72;"
        ),
    },
    "art:17:1:i": {
        EN: (
            "procedures related to the reporting of a serious incident in accordance with "
            "Article 73;"
        ),
        DE: "Verfahren zur Meldung eines schwerwiegenden Vorfalls gemäß Artikel 73;",
    },
    "art:17:1:j": {
        EN: (
            "the handling of communication with national competent authorities, other relevant "
            "authorities, including those providing or supporting the access to data, notified "
            "bodies, other operators, customers or other interested parties;"
        ),
        DE: (
            "die Handhabung der Kommunikation mit zuständigen nationalen Behörden, anderen "
            "einschlägigen Behörden, auch Behörden, die den Zugang zu Daten gewähren oder "
            "erleichtern, notifizierten Stellen, anderen Akteuren, Kunden oder sonstigen "
            "interessierten Kreisen;"
        ),
    },
    "art:17:1:k": {
        EN: (
            "systems and procedures for record-keeping of all relevant documentation and "
            "information;"
        ),
        DE: (
            "Systeme und Verfahren für die Aufzeichnung sämtlicher einschlägigen Dokumentation "
            "und Informationen;"
        ),
    },
    "art:17:1:l": {
        EN: "resource management, including security-of-supply related measures;",
        DE: (
            "Ressourcenmanagement, einschließlich Maßnahmen im Hinblick auf die "
            "Versorgungssicherheit;"
        ),
    },
    "art:17:1:m": {
        EN: (
            "an accountability framework setting out the responsibilities of the management "
            "and other staff with regard to all the aspects listed in this paragraph."
        ),
        DE: (
            "einen Rechenschaftsrahmen, der die Verantwortlichkeiten der Leitung und des "
            "sonstigen Personals in Bezug auf alle in diesem Absatz aufgeführten Aspekte "
            "regelt."
        ),
    },
    "art:27:1:a": {
        EN: (
            "a description of the deployer’s processes in which the high-risk AI system will "  # noqa: RUF001 (the Act's own apostrophe)
            "be used in line with its intended purpose;"
        ),
        DE: (
            "eine Beschreibung der Verfahren des Betreibers, bei denen das "
            "Hochrisiko-KI-System im Einklang mit seiner Zweckbestimmung verwendet wird;"
        ),
    },
    "art:27:1:b": {
        EN: (
            "a description of the period of time within which, and the frequency with which, "
            "each high-risk AI system is intended to be used;"
        ),
        DE: (
            "eine Beschreibung des Zeitraums und der Häufigkeit, innerhalb dessen bzw. mit der "
            "jedes Hochrisiko-KI-System verwendet werden soll;"
        ),
    },
    "art:27:1:c": {
        EN: (
            "the categories of natural persons and groups likely to be affected by its use in "
            "the specific context;"
        ),
        DE: (
            "die Kategorien der natürlichen Personen und Personengruppen, die von seiner "
            "Verwendung im spezifischen Kontext betroffen sein könnten;"
        ),
    },
    "art:27:1:d": {
        EN: (
            "the specific risks of harm likely to have an impact on the categories of natural "
            "persons or groups of persons identified pursuant to point (c) of this paragraph, "
            "taking into account the information given by the provider pursuant to Article 13;"
        ),
        DE: (
            "die spezifischen Schadensrisiken, die sich auf die gemäß Buchstabe c dieses "
            "Absatzes ermittelten Kategorien natürlicher Personen oder Personengruppen "
            "auswirken könnten, unter Berücksichtigung der vom Anbieter gemäß Artikel 13 "
            "bereitgestellten Informationen;"
        ),
    },
    "art:27:1:e": {
        EN: (
            "a description of the implementation of human oversight measures, according to the "
            "instructions for use;"
        ),
        DE: (
            "eine Beschreibung der Umsetzung von Maßnahmen der menschlichen Aufsicht "
            "entsprechend den Betriebsanleitungen;"
        ),
    },
    "art:27:1:f": {
        EN: (
            "the measures to be taken in the case of the materialisation of those risks, "
            "including the arrangements for internal governance and complaint mechanisms."
        ),
        DE: (
            "die Maßnahmen, die im Falle des Eintretens dieser Risiken zu ergreifen sind, "
            "einschließlich der Regelungen für die interne Unternehmensführung und "
            "Beschwerdemechanismen."
        ),
    },
}
