"""The technical documentation skeleton (Art. 11(1), Annex IV): one section per Annex IV point,
each asking one question per element the point lists.

The Omnibus lets SMEs and small mid-caps provide the Annex IV elements in a simplified form the
Commission is to publish; it hasn't yet (decision 007), so every company gets the full Annex IV
and an SME or a small mid-cap gets the note that a simplified form is expected (INIT >
Documentation drafting; decision 026, items 21 and 22).
"""

from aiact.drafting.models import SectionStatus
from aiact.drafting.skeletons.common import PREFILLED, ask, required
from aiact.drafting.templates import DE, EN, DocumentTemplate

SIMPLIFIED_FORM_NOTE = {
    EN: "A simplified form for SMEs and small mid-caps is expected (Art. 11(1)). Until the "
    "Commission publishes it, this is the full Annex IV.",
    DE: "Ein vereinfachtes Formular für KMU und kleine Midcap-Unternehmen wird erwartet "
    "(Art. 11 Abs. 1). Bis die Kommission es veröffentlicht, ist dies der vollständige "
    "Anhang IV.",
}

GENERAL_DESCRIPTION = required(
    "general_description",
    ("General description of the system", "Allgemeine Beschreibung des Systems"),
    "annex:IV:1",
    ask(
        "intended_purpose",
        "What is the system's intended purpose, who is its provider, and which version is this, "
        "in relation to earlier versions?",
        "Was ist die Zweckbestimmung des Systems, wer ist sein Anbieter, und welche Version ist "
        "dies, im Verhältnis zu früheren Versionen?",
    ),
    ask(
        "interactions",
        "Does the system interact with hardware or software that isn't part of it, including "
        "other AI systems? How?",
        "Interagiert das System mit Hardware oder Software, die nicht Teil des Systems ist, auch "
        "mit anderen KI-Systemen? Wie?",
    ),
    ask(
        "software_versions",
        "Which versions of software or firmware does it use, and what do version updates require?",
        "Welche Versionen von Software oder Firmware verwendet es, und was setzen Aktualisierungen "
        "voraus?",
    ),
    ask(
        "market_forms",
        "In which forms is it placed on the market or put into service, for example a software "
        "package, a download or an API?",
        "In welchen Formen wird es in Verkehr gebracht oder in Betrieb genommen, zum Beispiel "
        "als Softwarepaket, zum Herunterladen oder als API?",
    ),
    ask(
        "hardware",
        "What hardware is it intended to run on?",
        "Auf welcher Hardware soll es betrieben werden?",
    ),
    ask(
        "product_component",
        "Is it a component of a product? If so, which photographs or illustrations show the "
        "product's external features, marking and internal layout?",
        "Ist es Bestandteil eines Produkts? Wenn ja, welche Fotografien oder Abbildungen zeigen "
        "die äußeren Merkmale, die Kennzeichnung und den inneren Aufbau des Produkts?",
    ),
    ask(
        "user_interface",
        "What is the user interface provided to the deployer like, in brief?",
        "Wie ist die Benutzerschnittstelle, die dem Betreiber zur Verfügung steht, kurz "
        "beschrieben?",
    ),
    ask(
        "instructions_for_use",
        "Where are the instructions for use for the deployer?",
        "Wo finden sich die Betriebsanleitungen für den Betreiber?",
    ),
)

DEVELOPMENT = required(
    "development",
    ("Elements and development process", "Bestandteile und Entwicklungsprozess"),
    "annex:IV:2",
    ask(
        "development_methods",
        "Which methods and steps were used to develop the system, including any pre-trained "
        "systems or third-party tools, and how were those used, integrated or modified?",
        "Mit welchen Methoden und Schritten wurde das System entwickelt, einschließlich "
        "vortrainierter Systeme oder Instrumente Dritter, und wie wurden diese verwendet, "
        "integriert oder verändert?",
    ),
    ask(
        "design_specifications",
        "What are the design specifications: the general logic and algorithms, the key design "
        "choices with their rationale and assumptions, what the system optimises for, its "
        "expected output and output quality, and any trade-offs made to meet the requirements?",
        "Wie lauten die Entwurfsspezifikationen: die allgemeine Logik und die Algorithmen, die "
        "wichtigsten Entwurfsentscheidungen mit Gründen und Annahmen, was das System optimieren "
        "soll, die erwartete Ausgabe und ihre Qualität sowie Kompromisse zur Erfüllung der "
        "Anforderungen?",
    ),
    ask(
        "architecture",
        "How is the system built: how do its software components build on or feed into each "
        "other, and which computational resources were used to develop, train, test and "
        "validate it?",
        "Wie ist das System aufgebaut: wie bauen die Softwarekomponenten aufeinander auf oder "
        "arbeiten einander zu, und welche Rechenressourcen wurden zum Entwickeln, Trainieren, "
        "Testen und Validieren verwendet?",
    ),
    ask(
        "data_requirements",
        "Which training methods and data sets were used: their provenance, scope and main "
        "characteristics, and how the data was obtained, selected, labelled and cleaned?",
        "Welche Trainingsmethoden und Trainingsdatensätze wurden verwendet: Herkunft, Umfang und "
        "Hauptmerkmale, und wie wurden die Daten beschafft, ausgewählt, gekennzeichnet und "
        "bereinigt?",
    ),
    ask(
        "oversight_assessment",
        "Which human oversight measures does the system need (Art. 14), and which technical "
        "measures help deployers interpret its outputs?",
        "Welche Maßnahmen der menschlichen Aufsicht braucht das System (Art. 14), und welche "
        "technischen Maßnahmen erleichtern Betreibern die Interpretation seiner Ausgaben?",
    ),
    ask(
        "predetermined_changes",
        "Are changes to the system and its performance determined in advance? If so, what are "
        "they, and how do you make sure it keeps meeting the requirements?",
        "Sind Änderungen am System und an seiner Leistung vorab bestimmt? Wenn ja, welche, und "
        "wie stellen Sie sicher, dass es die Anforderungen weiterhin erfüllt?",
    ),
    ask(
        "validation_testing",
        "Which validation and testing procedures and data were used, and which metrics measure "
        "accuracy, robustness and potentially discriminatory impacts? Where are the dated and "
        "signed test logs and reports?",
        "Welche Validierungs- und Testverfahren und -daten wurden verwendet, und mit welchen "
        "Parametern werden Genauigkeit, Robustheit und potenziell diskriminierende Auswirkungen "
        "gemessen? Wo liegen die datierten und unterzeichneten Testprotokolle und -berichte?",
    ),
    ask(
        "cybersecurity",
        "Which cybersecurity measures are in place?",
        "Welche Cybersicherheitsmaßnahmen wurden ergriffen?",
    ),
)

MONITORING = required(
    "monitoring",
    ("Monitoring, functioning and control", "Überwachung, Funktionsweise und Kontrolle"),
    "annex:IV:3",
    ask(
        "capabilities_limitations",
        "What are the system's capabilities and limitations in performance, including its "
        "accuracy for the persons or groups it is used on and its expected accuracy overall?",
        "Was sind die Fähigkeiten und Leistungsgrenzen des Systems, einschließlich seiner "
        "Genauigkeit bei den Personen oder Gruppen, auf die es angewandt wird, und der insgesamt "
        "erwarteten Genauigkeit?",
    ),
    ask(
        "unintended_outcomes",
        "Which unintended outcomes and sources of risk to health, safety and fundamental rights, "
        "and of discrimination, can be foreseen?",
        "Welche unbeabsichtigten Ergebnisse und Quellen von Risiken für Gesundheit, Sicherheit "
        "und Grundrechte sowie von Diskriminierung sind vorhersehbar?",
    ),
    ask(
        "oversight_measures",
        "Which human oversight measures are in place, including the technical measures that "
        "help deployers interpret the outputs?",
        "Welche Maßnahmen der menschlichen Aufsicht bestehen, einschließlich der technischen "
        "Maßnahmen, die Betreibern die Interpretation der Ausgaben erleichtern?",
    ),
    ask(
        "input_data",
        "Which specifications apply to the input data, if any?",
        "Welche Spezifikationen gelten gegebenenfalls für die Eingabedaten?",
    ),
)

PERFORMANCE_METRICS = required(
    "performance_metrics",
    ("Performance metrics", "Leistungskennzahlen"),
    "annex:IV:4",
    ask(
        "metrics_appropriateness",
        "Which performance metrics do you use, and why are they appropriate for this system?",
        "Welche Leistungskennzahlen verwenden Sie, und warum sind sie für dieses System geeignet?",
    ),
)

RISK_MANAGEMENT = required(
    "risk_management",
    ("Risk management system", "Risikomanagementsystem"),
    "annex:IV:5",
    ask(
        "risk_management_system",
        "Describe the risk management system under Art. 9 in detail, or name the document that "
        "does.",
        "Beschreiben Sie das Risikomanagementsystem nach Art. 9 im Einzelnen, oder nennen Sie "
        "das Dokument, das es beschreibt.",
    ),
    waits_for=SectionStatus.TO_FILL_IN,
)

LIFECYCLE_CHANGES = required(
    "lifecycle_changes",
    ("Changes through the lifecycle", "Änderungen während des Lebenszyklus"),
    "annex:IV:6",
    ask(
        "relevant_changes",
        "Which relevant changes have you made to the system through its lifecycle?",
        "Welche einschlägigen Änderungen haben Sie während des Lebenszyklus am System vorgenommen?",
    ),
    waits_for=SectionStatus.TO_FILL_IN,
)

STANDARDS = required(
    "standards",
    ("Standards applied", "Angewandte Normen"),
    "annex:IV:7",
    ask(
        "harmonised_standards",
        "Which harmonised standards published in the Official Journal do you apply, in full or "
        "in part? If none, how do you meet the requirements, and which other standards and "
        "technical specifications do you apply?",
        "Welche im Amtsblatt veröffentlichten harmonisierten Normen wenden Sie vollständig oder "
        "teilweise an? Falls keine: wie erfüllen Sie die Anforderungen, und welche anderen Normen "
        "und technischen Spezifikationen wenden Sie an?",
    ),
    waits_for=SectionStatus.NEEDS_EVIDENCE,
)

DECLARATION_OF_CONFORMITY = required(
    "declaration_of_conformity",
    ("EU declaration of conformity", "EU-Konformitätserklärung"),
    "annex:IV:8",
    ask(
        "declaration_copy",
        "Once the EU declaration of conformity (Art. 47) is drawn up, where is its copy kept?",
        "Wo wird die Kopie der EU-Konformitätserklärung (Art. 47) aufbewahrt, sobald sie "
        "ausgestellt ist?",
    ),
    waits_for=SectionStatus.GENERATED_LAST,
)

POST_MARKET_MONITORING = required(
    "post_market_monitoring",
    ("Post-market monitoring", "Beobachtung nach dem Inverkehrbringen"),
    "annex:IV:9",
    ask(
        "post_market_plan",
        "How do you evaluate the system's performance once it is on the market (Art. 72), and "
        "where is the post-market monitoring plan (Art. 72(3))?",
        "Wie bewerten Sie die Leistung des Systems nach dem Inverkehrbringen (Art. 72), und wo "
        "liegt der Plan für die Beobachtung nach dem Inverkehrbringen (Art. 72 Abs. 3)?",
    ),
    waits_for=SectionStatus.TO_FILL_IN,
)

ANNEX_IV_SKELETON = DocumentTemplate(
    id="annex_iv_technical_documentation",
    article="art:11:1",
    title={EN: "Technical documentation (Annex IV)", DE: "Technische Dokumentation (Anhang IV)"},
    sections=(
        *PREFILLED,
        GENERAL_DESCRIPTION,
        DEVELOPMENT,
        MONITORING,
        PERFORMANCE_METRICS,
        RISK_MANAGEMENT,
        LIFECYCLE_CHANGES,
        STANDARDS,
        DECLARATION_OF_CONFORMITY,
        POST_MARKET_MONITORING,
    ),
    small_company_note=SIMPLIFIED_FORM_NOTE,
)
