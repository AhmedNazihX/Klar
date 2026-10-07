"""The risk management system skeleton (Art. 9): the system itself (paragraph 1), the four steps
of paragraph 2, the measures and residual risk (paragraph 5), testing (paragraphs 6 and 8) and
the impact on minors and vulnerable groups (paragraph 9).

Paragraphs 3, 4, 7 and 10 limit or permit rather than require something the document must
describe, so they have no section. The duty it answers is Art. 16(a): meeting the Section 2
requirements, Art. 9 among them.
"""

from aiact.drafting.models import SectionStatus
from aiact.drafting.skeletons.common import PREFILLED, ask, required
from aiact.drafting.templates import DE, EN, DocumentTemplate

PROCESS = required(
    "process",
    ("The risk management system", "Das Risikomanagementsystem"),
    "art:9:1",
    ask(
        "risk_owner",
        "Who establishes, implements and maintains the risk management system, and where is it "
        "documented?",
        "Wer richtet das Risikomanagementsystem ein, wendet es an und erhält es aufrecht, und wo "
        "ist es dokumentiert?",
    ),
    ask(
        "review_cycle",
        "How often is it reviewed and updated through the system's lifecycle?",
        "Wie oft wird es während des Lebenszyklus des Systems überprüft und aktualisiert?",
    ),
)

KNOWN_RISKS = required(
    "known_risks",
    ("Known and foreseeable risks", "Bekannte und vorhersehbare Risiken"),
    "art:9:2:a",
    ask(
        "known_risks",
        "Which known and reasonably foreseeable risks to health, safety or fundamental rights "
        "can the system pose when it is used as intended?",
        "Welche bekannten und vernünftigerweise vorhersehbaren Risiken für Gesundheit, "
        "Sicherheit oder Grundrechte können vom System bei bestimmungsgemäßer Verwendung "
        "ausgehen?",
    ),
)

RISK_ESTIMATION = required(
    "risk_estimation",
    ("Estimating and evaluating the risks", "Abschätzung und Bewertung der Risiken"),
    "art:9:2:b",
    ask(
        "risk_estimation",
        "How do you estimate and evaluate the risks, under intended use and under reasonably "
        "foreseeable misuse?",
        "Wie schätzen und bewerten Sie die Risiken, bei bestimmungsgemäßer Verwendung und bei "
        "vernünftigerweise vorhersehbarer Fehlanwendung?",
    ),
)

POST_MARKET_RISKS = required(
    "post_market_risks",
    ("Risks from post-market data", "Risiken aus der Beobachtung nach dem Inverkehrbringen"),
    "art:9:2:c",
    ask(
        "post_market_risks",
        "How do you evaluate other risks from the data your post-market monitoring gathers "
        "(Art. 72)?",
        "Wie bewerten Sie andere Risiken anhand der Daten aus Ihrer Beobachtung nach dem "
        "Inverkehrbringen (Art. 72)?",
    ),
)

RISK_MEASURES = required(
    "risk_measures",
    ("Risk management measures", "Risikomanagementmaßnahmen"),
    "art:9:2:d",
    ask(
        "risk_measures",
        "Which risk management measures address the risks you identified?",
        "Mit welchen Risikomanagementmaßnahmen begegnen Sie den ermittelten Risiken?",
    ),
)

RESIDUAL_RISK = required(
    "residual_risk",
    ("Residual risk", "Restrisiko"),
    "art:9:5",
    ask(
        "residual_risk",
        "Why is the residual risk of each hazard, and the overall residual risk, acceptable?",
        "Warum ist das Restrisiko jeder Gefahr und das Gesamtrestrisiko vertretbar?",
    ),
    ask(
        "risk_reduction",
        "How do design and development eliminate or reduce the risks, and which mitigation and "
        "control measures address those that can't be eliminated?",
        "Wie beseitigen oder verringern Konzeption und Entwicklung die Risiken, und welche "
        "Minderungs- und Kontrollmaßnahmen gelten für nicht auszuschließende Risiken?",
    ),
    ask(
        "deployer_information",
        "Which information (Art. 13) and, where appropriate, training do deployers get?",
        "Welche Informationen (Art. 13) und gegebenenfalls welche Schulung erhalten die Betreiber?",
    ),
)

TESTING = required(
    "testing",
    ("Testing", "Testen"),
    "art:9:6",
    ask(
        "testing",
        "Which tests identify the most appropriate risk management measures and show that the "
        "system performs consistently for its intended purpose? Where are the results?",
        "Mit welchen Tests ermitteln Sie die am besten geeigneten Risikomanagementmaßnahmen und "
        "zeigen, dass das System stets im Einklang mit seiner Zweckbestimmung funktioniert? Wo "
        "liegen die Ergebnisse?",
    ),
    waits_for=SectionStatus.NEEDS_EVIDENCE,
)

TEST_METRICS = required(
    "test_metrics",
    ("When and against what it is tested", "Wann und woran getestet wird"),
    "art:9:8",
    ask(
        "test_metrics",
        "When during development is the system tested, and against which metrics and "
        "probabilistic thresholds, defined beforehand?",
        "Wann während der Entwicklung wird das System getestet, und anhand welcher vorab "
        "festgelegten Metriken und Wahrscheinlichkeitsschwellenwerte?",
    ),
)

VULNERABLE_GROUPS = required(
    "vulnerable_groups",
    ("Minors and vulnerable groups", "Minderjährige und schutzbedürftige Gruppen"),
    "art:9:9",
    ask(
        "vulnerable_groups",
        "Is the system likely to have an adverse impact on people under 18 or other vulnerable "
        "groups? How have you considered this?",
        "Wird das System wahrscheinlich nachteilige Auswirkungen auf Personen unter 18 Jahren "
        "oder andere schutzbedürftige Gruppen haben? Wie haben Sie das berücksichtigt?",
    ),
)

ART_9_SKELETON = DocumentTemplate(
    id="art_9_risk_management",
    article="art:16:a",
    title={EN: "Risk management system (Art. 9)", DE: "Risikomanagementsystem (Art. 9)"},
    sections=(
        *PREFILLED,
        PROCESS,
        KNOWN_RISKS,
        RISK_ESTIMATION,
        POST_MARKET_RISKS,
        RISK_MEASURES,
        RESIDUAL_RISK,
        TESTING,
        TEST_METRICS,
        VULNERABLE_GROUPS,
    ),
)
