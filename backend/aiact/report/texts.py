"""The reports' wording, in English and German (P25; artboard `ExportPDF`).

The class, status and role names are the screens' (`frontend/src/i18n/locales`), and the German
terms the official text's (`docs/design-system/localisation.md`): Betreiber, Anbieter, Einführer,
Händler.
"""

from collections.abc import Mapping
from types import MappingProxyType

from aiact.schemas import EvidenceTag, Language, RiskClass, Role, Status, StepName

EN, DE = Language.EN, Language.DE
EN_DASH = "\u2013"

type ByLanguage = Mapping[Language, str]


def _texts(en: str, de: str) -> ByLanguage:
    return MappingProxyType({EN: en, DE: de})


CLASS_NAMES: Mapping[RiskClass, ByLanguage] = {
    RiskClass.PROHIBITED: _texts("Prohibited", "Verboten"),
    RiskClass.HIGH_RISK: _texts("High-risk", "Hochrisiko"),
    RiskClass.LIMITED_RISK: _texts("Limited risk", "Begrenztes Risiko"),
    RiskClass.MINIMAL_RISK: _texts("Minimal risk", "Minimales Risiko"),
    RiskClass.OUT_OF_SCOPE: _texts("Out of scope", "Außerhalb des Anwendungsbereichs"),
}
ASSUMED_CLASS = _texts("{name} (assumed)", "{name} (angenommen)")
"""A class that is the working assumption of an uncertain result."""
NOT_CLASSIFIED = _texts("Not classified yet", "Noch nicht eingestuft")

STATUS_NAMES: Mapping[Status, ByLanguage] = {
    Status.DECIDED: _texts("Decided", "Festgestellt"),
    Status.NEEDS_MORE_INFORMATION: _texts("Needs more information", "Weitere Angaben nötig"),
    Status.LEGALLY_AMBIGUOUS: _texts("Legally ambiguous", "Rechtlich unklar"),
}

ROLE_NAMES: Mapping[Role, ByLanguage] = {
    Role.PROVIDER: _texts("Provider", "Anbieter"),
    Role.DEPLOYER: _texts("Deployer", "Betreiber"),
    Role.IMPORTER: _texts("Importer", "Einführer"),
    Role.DISTRIBUTOR: _texts("Distributor", "Händler"),
}
ROLE_OF: Mapping[Role, ByLanguage] = {
    Role.PROVIDER: _texts("the provider", "des Anbieters"),
    Role.DEPLOYER: _texts("the deployer", "des Betreibers"),
    Role.IMPORTER: _texts("the importer", "des Einführers"),
    Role.DISTRIBUTOR: _texts("the distributor", "des Händlers"),
}
"""A role as the duties' heading names it: "Duties of the deployer", "Pflichten des Betreibers"."""
NO_ROLE = _texts("Not determined", "Nicht ermittelt")
NOTHING = EN_DASH
"""An empty cell."""

EVIDENCE: Mapping[EvidenceTag, ByLanguage] = {
    EvidenceTag.STATED: _texts("Stated by the user", "In der Beschreibung angegeben"),
    EvidenceTag.INFERRED: _texts(
        "Inferred by Klar from the description", "Von Klar aus der Beschreibung abgeleitet"
    ),
    EvidenceTag.ASSUMED: _texts("Assumed, not yet confirmed", "Angenommen, noch nicht bestätigt"),
}

STEP_NAMES: Mapping[StepName, ByLanguage] = {
    StepName.ROLE_OBLIGATIONS: _texts("Role", "Rolle"),
    StepName.SCOPE: _texts("1 Scope", "1 Anwendungsbereich"),
    StepName.PROHIBITED: _texts("2 Prohibited practices", "2 Verbotene Praktiken"),
    StepName.HIGH_RISK: _texts("3 High-risk", "3 Hochrisiko"),
    StepName.TRANSPARENCY: _texts("4 Transparency", "4 Transparenz"),
}
STEP_REFERENCES: Mapping[StepName, ByLanguage] = {
    StepName.ROLE_OBLIGATIONS: _texts(f"Art. 16, 23{EN_DASH}26", f"Art. 16, 23{EN_DASH}26"),
    StepName.SCOPE: _texts(f"Art. 2{EN_DASH}3", f"Art. 2{EN_DASH}3"),
    StepName.PROHIBITED: _texts("Art. 5", "Art. 5"),
    StepName.HIGH_RISK: _texts("Art. 6, Annex I and III", "Art. 6, Anhang I und III"),
    StepName.TRANSPARENCY: _texts("Art. 50", "Art. 50"),
}
"""What a step checks, for a step that cites no provision of the Act (the screens' references)."""
STEP_OUTCOMES: Mapping[str, ByLanguage] = MappingProxyType(
    {
        "notChecked": _texts("Not checked", "Nicht geprüft"),
        "paused": _texts("Waiting for your answer", "Wartet auf Ihre Antwort"),
        "ambiguous": _texts(
            "Legally ambiguous: the stricter reading applies",
            "Rechtlich unklar: Es gilt die strengere Lesart",
        ),
        "inScope": _texts("In scope", "Anwendbar"),
        "outOfScope": _texts("Out of scope", "Außerhalb des Anwendungsbereichs"),
        "noBan": _texts(
            "No match with a banned practice", "Kein Treffer bei den verbotenen Praktiken"
        ),
        "ban": _texts("Matches a banned practice", "Entspricht einer verbotenen Praktik"),
        "highRiskAnnexIII": _texts("Yes: {label}", "Ja: {label}"),
        "highRiskAnnexI": _texts(
            "Yes: part of a product under Annex I", "Ja: Teil eines Produkts nach Anhang I"
        ),
        "highRisk": _texts("Yes: high-risk", "Ja: Hochrisiko"),
        "notHighRisk": _texts("Not high-risk", "Kein Hochrisiko"),
        "transparencyDuty": _texts("1 duty under Art. 50", "1 Pflicht nach Art. 50"),
        "transparencyDuties": _texts(
            "{count} duties under Art. 50", "{count} Pflichten nach Art. 50"
        ),
        "noTransparency": _texts("No separate duty found", "Keine eigene Pflicht gefunden"),
    }
)
"""A step's outcome in one plain line, as the Result screen's step rows say it
(`result.steps` in the locales, `stepOutcome` in `result-text.ts`)."""
ANNEX_III_LABELS: Mapping[str, ByLanguage] = MappingProxyType(
    {
        "III_1_a": _texts("remote biometric identification", "biometrische Fernidentifizierung"),
        "III_1_b": _texts(
            "biometric categorisation by sensitive attributes",
            "biometrische Kategorisierung nach sensiblen Merkmalen",
        ),
        "III_1_c": _texts("emotion recognition", "Emotionserkennung"),
        "III_2": _texts(
            "safety components of critical infrastructure",
            "Sicherheitsbauteile kritischer Infrastruktur",
        ),
        "III_3_a": _texts(
            "access or admission to education and training",
            "Zugang oder Zulassung zu Bildung und Ausbildung",
        ),
        "III_3_b": _texts("evaluating learning outcomes", "Bewertung von Lernergebnissen"),
        "III_3_c": _texts(
            "assessing the level of education a person can access",
            "Bewertung des angemessenen Bildungsniveaus",
        ),
        "III_3_d": _texts(
            "monitoring students during tests", "Überwachung von Prüflingen bei Prüfungen"
        ),
        "III_4_a": _texts(
            "recruitment and selection of people", "Einstellung und Auswahl von Personen"
        ),
        "III_4_b": _texts(
            "decisions about work relationships, tasks and performance",
            "Entscheidungen über Arbeitsverhältnisse, Aufgaben und Leistung",
        ),
        "III_5_a": _texts(
            "eligibility for public assistance benefits and services",
            "Anspruch auf öffentliche Unterstützungsleistungen und Dienste",
        ),
        "III_5_b": _texts(
            "creditworthiness and credit scores", "Kreditwürdigkeit und Bonitätsbewertung"
        ),
        "III_5_c": _texts(
            "risk assessment and pricing in life and health insurance",
            "Risikobewertung und Preisbildung bei Lebens- und Krankenversicherungen",
        ),
        "III_5_d": _texts(
            "emergency calls, dispatch and patient triage",
            "Notrufe, Einsatzsteuerung und Triage",
        ),
        "III_6_a": _texts(
            "assessing the risk of becoming a victim of crime",
            "Risiko, Opfer einer Straftat zu werden",
        ),
        "III_6_b": _texts(
            "polygraphs and similar tools in law enforcement",
            "Lügendetektoren und ähnliche Instrumente bei der Strafverfolgung",
        ),
        "III_6_c": _texts(
            "assessing the reliability of evidence",
            "Bewertung der Verlässlichkeit von Beweismitteln",
        ),
        "III_6_d": _texts(
            "assessing the risk of offending or reoffending",
            "Risiko einer Straftat oder erneuten Straftat",
        ),
        "III_6_e": _texts(
            "profiling in criminal investigations", "Profiling bei strafrechtlichen Ermittlungen"
        ),
        "III_7_a": _texts(
            "polygraphs and similar tools at borders",
            "Lügendetektoren und ähnliche Instrumente an Grenzen",
        ),
        "III_7_b": _texts(
            "risk assessment of people entering the EU",
            "Risikobewertung von Personen bei der Einreise",
        ),
        "III_7_c": _texts(
            "examining asylum, visa and residence applications",
            "Prüfung von Asyl-, Visums- und Aufenthaltsanträgen",
        ),
        "III_7_d": _texts(
            "detecting, recognising or identifying people in migration",
            "Aufdeckung, Erkennung oder Identifizierung von Personen bei der Migration",
        ),
        "III_8_a": _texts(
            "assisting courts in researching and applying the law",
            "Unterstützung von Gerichten bei der Ermittlung und Anwendung des Rechts",
        ),
        "III_8_b": _texts(
            "influencing elections or referendums",
            "Beeinflussung von Wahlen oder Abstimmungen",
        ),
    }
)
"""An Annex III point's plain label, as the screens name it (`annexPoint` in the locales)."""
FOOTER = _texts("Prepared with Klar, an AI system.", "Erstellt mit Klar, einem KI-System.")
PREPARED = _texts("Prepared on {date}.", "Erstellt am {date}.")
LAW_LINES: Mapping[bool, ByLanguage] = {
    True: _texts(
        "Checked under Regulation (EU) 2024/1689 as amended, consolidated text of {version} "
        "(CELEX {celex}), as it applies on {as_of}.",
        "Geprüft nach der Verordnung (EU) 2024/1689 in geänderter Fassung, konsolidierter Text "
        "vom {version} (CELEX {celex}), wie sie am {as_of} gilt.",
    ),
    False: _texts(
        "Checked under Regulation (EU) 2024/1689 as published on {version} (CELEX {celex}), "
        "as it applies on {as_of}.",
        "Geprüft nach der Verordnung (EU) 2024/1689 in der am {version} veröffentlichten "
        "Fassung (CELEX {celex}), wie sie am {as_of} gilt.",
    ),
}
"""The law line, by whether the text is the amended one."""

UNNAMED_TOOL = _texts("Your tool", "Ihr Tool")
KICKER = _texts("Classification report · Report {id}", "Bericht zur Einstufung · Bericht {id}")

FIELD_LABELS = MappingProxyType(
    {
        "class": _texts("Class", "Einstufung"),
        "status": _texts("Status", "Status"),
        "role": _texts("Role", "Rolle"),
        "from": _texts("Duties apply from", "Pflichten gelten ab"),
    }
)
NO_DUTIES_DATE = _texts("No specific duties", "Keine besonderen Pflichten")
STOP_USING = _texts(
    "Stop using or supplying it now", "Nutzen oder liefern Sie es ab sofort nicht mehr"
)
"""A prohibited tool's line, as the inventory's "needs you" says it (`inventory.needs`); the
report's paragraph adds the full stop."""

BASIS = _texts("Basis", "Grundlage")
BASIS_ANNEX_III = _texts(
    "The tool is listed in {point}: {label}.", "Das Tool ist in {point} aufgeführt: {label}."
)
BASIS_ANNEX_III_PLAIN = _texts(
    "The tool is listed in {point}.", "Das Tool ist in {point} aufgeführt."
)
BASIS_ANNEX_I = _texts(
    "The tool is part of a product covered by {point}.",
    "Das Tool ist Teil eines Produkts, das unter {point} fällt.",
)
CLASS_BASIS: Mapping[RiskClass, ByLanguage] = {
    RiskClass.HIGH_RISK: _texts("The tool is high-risk.", "Das Tool ist ein Hochrisiko-System."),
    RiskClass.PROHIBITED: _texts(
        "It matches a practice banned by Art. 5.",
        "Es entspricht einer nach Art. 5 verbotenen Praktik.",
    ),
    RiskClass.LIMITED_RISK: _texts(
        "Transparency duties under Art. 50 apply.", "Es gelten Transparenzpflichten nach Art. 50."
    ),
    RiskClass.MINIMAL_RISK: _texts(
        "It isn't banned, isn't high-risk and has no Art. 50 duty.",
        "Es ist weder verboten noch ein Hochrisiko-System und hat keine Pflicht nach Art. 50.",
    ),
    RiskClass.OUT_OF_SCOPE: _texts(
        "The AI Act doesn't apply to it.", "Die KI-Verordnung gilt dafür nicht."
    ),
}
"""The basis, as the Result screen says it (`result.basis` in the locales, `basisSentence`)."""
FACTS = _texts("Facts the result rests on", "Fakten, auf denen das Ergebnis beruht")
FACT_HEADER = (_texts("Fact", "Fakt"), _texts("Source", "Quelle"))
NO_FACTS = _texts("The result lists no facts.", "Das Ergebnis nennt keine Fakten.")
STEPS = _texts("How the result was reached", "Wie das Ergebnis zustande kam")
PAUSED_STEPS = _texts("Where the checks stand", "Stand der Prüfungen")
"""The steps' heading on a result waiting for an answer, as the Result screen says it."""
STEP_HEADER = (
    _texts("Step", "Schritt"),
    _texts("Decision", "Entscheidung"),
    _texts("Provision", "Vorschrift"),
)

DUTIES = _texts("Duties", "Pflichten")
DUTIES_OF = _texts("Duties of {role}", "Pflichten {role}")
ROLES_JOINED = _texts("{first} and {second}", "{first} und {second}")
WHEN = _texts("{what}, {when}", "{what}, {when}")
"""A duty table's heading, or a duty's provision, with when it applies."""
FROM_DATE = _texts("from {date}", "ab dem {date}")
ONLY_AFTER_CHANGE = _texts(
    "only after a significant change ({article})",
    "nur nach einer erheblichen Änderung ({article})",
)
"""After a heading or a provision; a cell of its own starts it with a capital."""
DUTY_HEADER = (_texts("Duty", "Pflicht"), _texts("Provision", "Vorschrift"))
FROM_HEADER = _texts("Applies from", "Gilt ab")
NO_DUTIES = _texts(
    "The result lists no specific duties for this tool.",
    "Das Ergebnis nennt für dieses Tool keine besonderen Pflichten.",
)
LEFT_OUT: Mapping[bool, ByLanguage] = {
    True: _texts(
        "1 more duty the result lists is not in Klar's table of duties, so it is left out here.",
        "1 weitere Pflicht, die das Ergebnis nennt, steht nicht in Klars Pflichtentabelle und "
        "fehlt deshalb hier.",
    ),
    False: _texts(
        "{count} more duties the result lists are not in Klar's table of duties, so they are "
        "left out here.",
        "{count} weitere Pflichten, die das Ergebnis nennt, stehen nicht in Klars "
        "Pflichtentabelle und fehlen deshalb hier.",
    ),
}
"""Posted duties no entry of the obligations table matches (`aiact.report.duties`), by whether
there is exactly one."""
APPLIES_IF = _texts("{duty} Applies if: {condition}", "{duty} Gilt, wenn: {condition}")
LEGACY_FROM = _texts("{date} ({article})", "{date} ({article})")

LEGAL_REVIEW = _texts("Points for legal review", "Punkte für die rechtliche Prüfung")
ASSUMED_FACTS = _texts(
    "These facts the result rests on are assumed and should be confirmed:",
    "Diese Fakten, auf denen das Ergebnis beruht, sind angenommen und sollten bestätigt werden:",
)
LISTED = _texts(f"{EN_DASH} {{text}}", f"{EN_DASH} {{text}}")
OPEN_QUESTION = _texts(
    "Open question of law ({step}): {question}", "Offene Rechtsfrage ({step}): {question}"
)
MISSING_FACT = _texts("Missing fact ({step}): {question}", "Fehlende Angabe ({step}): {question}")
NOTHING_TO_REVIEW = _texts(
    "No fact the result rests on is assumed, and no question is open.",
    "Keine Tatsache, auf der das Ergebnis beruht, ist angenommen, und keine Frage ist offen.",
)

REVIEWER = _texts("For the reviewer", "Für die prüfende Person")
REVIEWER_LABELS = (_texts("Reviewed by", "Geprüft von"), _texts("Date", "Datum"))
REVIEWER_TEXT = _texts(
    "This report sets out how Klar applied the AI Act to the facts provided. It is not legal "
    "advice and does not state whether the company complies with the law. The provisions it "
    "cites are those of the text named above.",
    "Dieser Bericht legt dar, wie Klar die KI-Verordnung auf die angegebenen Fakten angewandt "
    "hat. Er ist keine Rechtsberatung und sagt nicht, ob das Unternehmen das Recht einhält. Die "
    "genannten Vorschriften sind die des oben bezeichneten Textes.",
)

INVENTORY_KICKER = _texts("Inventory report", "Inventarbericht")
INVENTORY_TITLE = _texts("Your AI inventory", "Ihr KI-Inventar")
TOOL_COUNT: Mapping[bool, ByLanguage] = {
    True: _texts("1 tool.", "1 Tool."),
    False: _texts("{count} tools.", "{count} Tools."),
}
"""The tool count, by whether there is exactly one."""
INVENTORY_NOTE = _texts(
    "Each result is shown as Klar gave it when the tool was checked. Klar doesn't check a "
    "stored result again.",
    "Jedes Ergebnis steht so da, wie Klar es bei der Prüfung des Tools ausgegeben hat. Klar "
    "prüft ein gespeichertes Ergebnis nicht erneut.",
)
INVENTORY_HEADER = (
    _texts("Tool", "Tool"),
    _texts("Class", "Einstufung"),
    _texts("Status", "Status"),
    _texts("Role", "Rolle"),
    _texts("Duties apply from", "Pflichten gelten ab"),
)
NO_TOOLS = _texts("The inventory has no tools yet.", "Das Inventar enthält noch keine Tools.")
TOOL_LAW: Mapping[bool, ByLanguage] = {
    True: _texts(
        "Checked under the amended text, as it applies on {as_of}.",
        "Geprüft nach der geänderten Fassung, wie sie am {as_of} gilt.",
    ),
    False: _texts(
        "Checked under the original 2024 text, as it applies on {as_of}.",
        "Geprüft nach der ursprünglichen Fassung von 2024, wie sie am {as_of} gilt.",
    ),
}
"""A tool's law line in the inventory report, by whether the text is the amended one."""

CHECKLIST_KICKER = _texts("Obligations checklist", "Pflichten-Checkliste")
CHECKLIST_TITLE = _texts("Your obligations", "Ihre Pflichten")
DONE_COUNT = _texts("{done} of {total} done.", "{done} von {total} erledigt.")
"""Ticked duties of the tickable ones (the Obligations screen's "N of M done")."""
NOT_CHECKED_WORK = _texts(
    "Klar keeps the list; it doesn't check the work for you.",
    "Klar führt die Liste; ob die Arbeit getan ist, prüft Klar nicht.",
)
"""Said wherever progress shows (decision 026 item 9); the screens' `obligations.notChecked`."""
CHECKLIST_NOTE = _texts(
    "A duty marked done is one you ticked off in Klar.",
    "Als erledigt markiert ist eine Pflicht, die Sie in Klar abgehakt haben.",
)
CHECKLIST_LAW: Mapping[bool, ByLanguage] = {
    True: _texts(
        "Dates under Regulation (EU) 2024/1689 as amended, consolidated text of {version} "
        "(CELEX {celex}).",
        "Daten nach der Verordnung (EU) 2024/1689 in geänderter Fassung, konsolidierter Text "
        "vom {version} (CELEX {celex}).",
    ),
    False: _texts(
        "Dates under Regulation (EU) 2024/1689 as published on {version} (CELEX {celex}).",
        "Daten nach der Verordnung (EU) 2024/1689 in der am {version} veröffentlichten "
        "Fassung (CELEX {celex}).",
    ),
}
"""The law text the checklist's dates follow, the one the Obligations screen showed, by whether
it is the amended one."""
ORIGINAL_DATES = _texts(
    "Dates follow the original Art. 113. The duties shown are the amended text's.",
    "Die Daten folgen dem ursprünglichen Art. 113. Die angezeigten Pflichten sind die der "
    "geänderten Fassung.",
)
"""Under the original text only the high-risk route dates swap (decision 026 item 11); the
screens' `result.todo.originalDates`."""
STRICTER_READING = _texts(
    "These duties apply if the stricter reading holds.",
    "Diese Pflichten gelten, wenn die strengere Auslegung zutrifft.",
)
"""An assumed class (needs more information, legally ambiguous) never reads as settled."""
STATE_HEADER = _texts("Status", "Stand")
DONE_STATES: Mapping[bool, ByLanguage] = {
    True: _texts("Done", "Erledigt"),
    False: _texts("Open", "Offen"),
}
"""A duty's ticked state in the checklist, by whether the user ticked it off."""
