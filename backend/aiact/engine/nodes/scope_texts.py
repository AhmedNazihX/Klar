"""The fixed texts of the scope node (E3): the deciding key facts with their stable follow-up
ids, the provisions they rest on and why each takes a system out of scope, and the decision
sentences, in English and German."""

from collections.abc import Mapping
from dataclasses import dataclass

from aiact.schemas import Language


@dataclass(frozen=True)
class ScopeQuestion:
    """A deciding scope fact: its follow-up question, the provision and recitals it rests on,
    and why the Act doesn't apply when the fact takes the system out of scope."""

    id: str
    """The follow-up question's id, and the field of the model's answer."""
    article: str
    recitals: tuple[str, ...]
    question: Mapping[Language, str]
    reason: Mapping[Language, str] | None = None


AI_SYSTEM = ScopeQuestion(
    id="ai_system",
    article="art:3:1",
    recitals=("recital:12",),
    question={
        Language.EN: "How does the system produce its outputs: is it trained on data or does it "
        "otherwise infer them, or does it only apply rules or calculations that people defined?",
        Language.DE: "Wie erzeugt das System seine Ergebnisse: Wurde es mit Daten trainiert oder "
        "leitet es sie auf andere Weise ab, oder wendet es nur von Menschen festgelegte Regeln "
        "oder Berechnungen an?",
    },
    reason={
        Language.EN: "Art. 3(1): it is not an AI system, because it does not infer from the "
        "input it receives how to generate its outputs (recital 12).",
        Language.DE: "Art. 3 Nr. 1: Es ist kein KI-System, weil es nicht aus den erhaltenen "
        "Eingaben ableitet, wie es seine Ausgaben erzeugt (Erwägungsgrund 12).",
    },
)
EU_LINK = ScopeQuestion(
    id="eu_link",
    article="art:2:1",
    recitals=(),
    question={
        Language.EN: "Is the system placed on the market or used in the EU, or is its output "
        "used in the EU?",
        Language.DE: "Wird das System in der EU in Verkehr gebracht oder genutzt, oder werden "
        "seine Ergebnisse in der EU verwendet?",
    },
    reason={
        Language.EN: "Art. 2(1): it has no link to the Union: it is not placed on the market or "
        "put into service there, no provider or deployer is established there, and its output "
        "is not used there.",
        Language.DE: "Art. 2 Abs. 1: Es hat keinen Bezug zur Union: Es wird dort weder in "
        "Verkehr gebracht noch in Betrieb genommen, kein Anbieter oder Betreiber ist dort "
        "niedergelassen, und seine Ausgaben werden dort nicht verwendet.",
    },
)
MILITARY_ONLY = ScopeQuestion(
    id="military_only",
    article="art:2:3",
    recitals=("recital:24",),
    question={
        Language.EN: "Is the system used exclusively for military, defence or national security "
        "purposes, with no civilian or law-enforcement use?",
        Language.DE: "Wird das System ausschließlich für militärische Zwecke, Verteidigungszwecke "
        "oder Zwecke der nationalen Sicherheit verwendet, ohne zivile Nutzung und ohne Nutzung "
        "zur Strafverfolgung?",
    },
    reason={
        Language.EN: "Art. 2(3): it is placed on the market, put into service or used "
        "exclusively for military, defence or national security purposes.",
        Language.DE: "Art. 2 Abs. 3: Es wird ausschließlich für militärische Zwecke, "
        "Verteidigungszwecke oder Zwecke der nationalen Sicherheit in Verkehr gebracht, in "
        "Betrieb genommen oder verwendet.",
    },
)
RESEARCH_ONLY = ScopeQuestion(
    id="research_only",
    article="art:2:6",
    recitals=("recital:25",),
    question={
        Language.EN: "Is the system developed and put into service solely for scientific "
        "research and development, with no other use or offer?",
        Language.DE: "Wird das System ausschließlich für die wissenschaftliche Forschung und "
        "Entwicklung entwickelt und in Betrieb genommen, ohne andere Nutzung oder Angebot?",
    },
    reason={
        Language.EN: "Art. 2(6): it is specifically developed and put into service only for "
        "scientific research and development.",
        Language.DE: "Art. 2 Abs. 6: Es wird eigens für den alleinigen Zweck der "
        "wissenschaftlichen Forschung und Entwicklung entwickelt und in Betrieb genommen.",
    },
)
PRE_MARKET_DEVELOPMENT = ScopeQuestion(
    id="pre_market_development",
    article="art:2:8",
    recitals=("recital:25",),
    question={
        Language.EN: "Is the system still only being researched, developed or tested, before it "
        "is placed on the market or put into service, with no testing in real-world conditions?",
        Language.DE: "Wird das System noch ausschließlich erforscht, entwickelt oder getestet, "
        "bevor es in Verkehr gebracht oder in Betrieb genommen wird, ohne Tests unter "
        "Realbedingungen?",
    },
    reason={
        Language.EN: "Art. 2(8): it is only being researched, developed or tested before it is "
        "placed on the market or put into service, and not tested in real-world conditions.",
        Language.DE: "Art. 2 Abs. 8: Es wird nur erforscht, entwickelt oder getestet, bevor es "
        "in Verkehr gebracht oder in Betrieb genommen wird, und nicht unter Realbedingungen "
        "getestet.",
    },
)
PERSONAL_USE = ScopeQuestion(
    id="personal_use",
    article="art:2:10",
    recitals=(),
    question={
        Language.EN: "Are you using the system as a private individual, purely for personal, "
        "non-professional purposes?",
        Language.DE: "Nutzen Sie das System als Privatperson, ausschließlich für persönliche, "
        "nicht berufliche Zwecke?",
    },
    reason={
        Language.EN: "Art. 2(10): it is used by a natural person in the course of a purely "
        "personal, non-professional activity.",
        Language.DE: "Art. 2 Abs. 10: Es wird von einer natürlichen Person im Rahmen einer "
        "ausschließlich persönlichen und nicht beruflichen Tätigkeit verwendet.",
    },
)
OPEN_SOURCE = ScopeQuestion(
    id="open_source",
    article="art:2:12",
    recitals=("recital:102", "recital:103"),
    question={
        Language.EN: "Is the system released under a free and open-source licence, without "
        "being monetised?",
        Language.DE: "Wird das System unter einer freien und quelloffenen Lizenz bereitgestellt, "
        "ohne dass es monetarisiert wird?",
    },
    reason={
        Language.EN: "Art. 2(12): it is released under a free and open-source licence and is "
        "not placed on the market or put into service as a high-risk AI system or as a system "
        "that falls under Art. 5 or 50.",
        Language.DE: "Art. 2 Abs. 12: Es wird unter einer freien und quelloffenen Lizenz "
        "bereitgestellt und weder als Hochrisiko-KI-System noch als System, das unter Art. 5 "
        "oder 50 fällt, in Verkehr gebracht oder in Betrieb genommen.",
    },
)
OPEN_SOURCE_EXCEPTION = ScopeQuestion(
    id="open_source_exception",
    article="art:2:12",
    recitals=(),
    question={
        Language.EN: "Is the system placed on the market or put into service for a use that may "
        "make it high-risk (an Annex III use, or a safety component under Annex I), or does it "
        "fall under Art. 5 (prohibited practices) or Art. 50 (for example because it interacts "
        "with people or generates content)?",
        Language.DE: "Wird das System für eine Verwendung in Verkehr gebracht oder in Betrieb "
        "genommen, die es hochriskant machen kann (eine Verwendung nach Anhang III oder ein "
        "Sicherheitsbauteil nach Anhang I), oder fällt es unter Art. 5 (verbotene Praktiken) "
        "oder Art. 50 (zum Beispiel, weil es mit Menschen interagiert oder Inhalte erzeugt)?",
    },
)

EXCLUSIONS: tuple[ScopeQuestion, ...] = (
    EU_LINK,
    MILITARY_ONLY,
    RESEARCH_ONLY,
    PRE_MARKET_DEVELOPMENT,
    PERSONAL_USE,
    OPEN_SOURCE,
)
"""The Art. 2 rules that can take an AI system out of scope, in the Act's order."""

OPEN_QUESTION: Mapping[Language, str] = {
    Language.EN: "Is the system an AI system under Art. 3(1)?",
    Language.DE: "Ist das System ein KI-System im Sinne von Art. 3 Nr. 1?",
}
READINGS: Mapping[Language, tuple[str, str]] = {
    Language.EN: (
        "It is an AI system: the Act applies, and the remaining checks decide its class (the "
        "stricter reading, assumed here).",
        "It is not an AI system: the Act does not apply (out of scope).",
    ),
    Language.DE: (
        "Es ist ein KI-System: Die Verordnung gilt, und die weiteren Prüfungen bestimmen seine "
        "Klasse (die strengere Lesart, hier angenommen).",
        "Es ist kein KI-System: Die Verordnung gilt nicht (nicht anwendbar).",
    ),
}
"""The two readings of an open Art. 3(1) question, stricter first."""

TEXTS: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "out_of_scope": "Out of scope: the AI Act does not apply.",
        "in_scope": "In scope: an AI system under Art. 3(1), and no Art. 2 exclusion applies.",
        "ambiguous": "Legally ambiguous: Art. 3(1) and the Commission's definition guidelines "
        "don't settle whether this is an AI system. Working assumption: it is, so the remaining "
        "checks run.",
        "assumption": "Working assumption: in scope, pending an answer to: {question}",
        "still_asked": "Still to confirm: {question}",
    },
    Language.DE: {
        "out_of_scope": "Nicht anwendbar: Die KI-Verordnung gilt nicht.",
        "in_scope": "Anwendbar: ein KI-System im Sinne von Art. 3 Nr. 1, und keine Ausnahme nach "
        "Art. 2 greift.",
        "ambiguous": "Rechtlich offen: Art. 3 Nr. 1 und die Leitlinien der Kommission zur "
        "Definition klären nicht, ob dies ein KI-System ist. Arbeitsannahme: Es ist eines, "
        "daher laufen die weiteren Prüfungen.",
        "assumption": "Arbeitsannahme: anwendbar, bis diese Frage beantwortet ist: {question}",
        "still_asked": "Noch zu bestätigen: {question}",
    },
}
