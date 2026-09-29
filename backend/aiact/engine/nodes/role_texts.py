"""The fixed texts of the role and obligations node (E7): the deciding key facts with their
stable follow-up ids and the articles they rest on, role names, and the decision sentences, in
English and German."""

from collections.abc import Mapping
from dataclasses import dataclass

from aiact.schemas import Language, Role


@dataclass(frozen=True)
class KeyQuestion:
    """A deciding fact: its follow-up question and, when a "yes" makes a provider, why."""

    id: str
    article: str
    question: Mapping[Language, str]
    reason: Mapping[Language, str] | None = None


ROLE_ARTICLES: Mapping[Role, str] = {
    Role.PROVIDER: "art:3:3",
    Role.DEPLOYER: "art:3:4",
    Role.IMPORTER: "art:3:6",
    Role.DISTRIBUTOR: "art:3:7",
}
"""The Art. 3 definition each role rests on."""


OPERATOR_ROLE = KeyQuestion(
    id="operator_role",
    article="art:3:3",
    question={
        Language.EN: "Does your company develop the system, use a system someone else provides, "
        "import it into the EU, or distribute it?",
        Language.DE: "Entwickelt Ihr Unternehmen das System, nutzt es ein System eines anderen "
        "Anbieters, führt es das System in die EU ein oder vertreibt es es?",
    },
)
BUILDS_ON_GPAI = KeyQuestion(
    id="builds_on_gpai",
    article="art:3:68",
    question={
        Language.EN: "Is the system built on a general-purpose AI model from another provider "
        "(for example a foundation model integrated through an API)?",
        Language.DE: "Beruht das System auf einem KI-Modell mit allgemeinem Verwendungszweck eines "
        "anderen Anbieters (zum Beispiel ein über eine API eingebundenes Basismodell)?",
    },
    reason={
        Language.EN: "It builds its own system on a general-purpose AI model, so it is the "
        "provider of that system; the model provider's own duties (Art. 53) are flagged.",
        Language.DE: "Es baut ein eigenes System auf einem KI-Modell mit allgemeinem "
        "Verwendungszweck auf und ist daher dessen Anbieter; die eigenen Pflichten des "
        "Modellanbieters (Art. 53) werden ausgewiesen.",
    },
)
SWITCHES: Mapping[str, KeyQuestion] = {
    "own_brand": KeyQuestion(
        id="own_brand",
        article="art:25:1:a",
        question={
            Language.EN: "Do you put your own name or trademark on the system?",
            Language.DE: "Bringen Sie Ihren eigenen Namen oder Ihre Marke auf dem System an?",
        },
        reason={
            Language.EN: "Art. 25(1)(a): it puts its own name or trademark on the high-risk "
            "system, so it is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. a: Es bringt seinen Namen oder seine Marke auf "
            "dem Hochrisiko-System an und gilt daher als dessen Anbieter.",
        },
    ),
    "substantial_modification": KeyQuestion(
        id="substantial_modification",
        article="art:25:1:b",
        question={
            Language.EN: "Have you changed the system beyond the provider's configuration "
            "options, for example by retraining it or changing how it decides?",
            Language.DE: "Haben Sie das System über die Einstellmöglichkeiten des Anbieters "
            "hinaus verändert, zum Beispiel neu trainiert oder seine Entscheidungslogik geändert?",
        },
        reason={
            Language.EN: "Art. 25(1)(b): it substantially modifies the high-risk system, so it "
            "is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. b: Es nimmt eine wesentliche Veränderung am "
            "Hochrisiko-System vor und gilt daher als dessen Anbieter.",
        },
    ),
    "changed_purpose": KeyQuestion(
        id="changed_purpose",
        article="art:25:1:c",
        question={
            Language.EN: "Do you use the system for a purpose its provider did not intend?",
            Language.DE: "Nutzen Sie das System für einen Zweck, den sein Anbieter nicht "
            "vorgesehen hat?",
        },
        reason={
            Language.EN: "Art. 25(1)(c): it uses the system for a new purpose that makes it "
            "high-risk, so it is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. c: Es ändert die Zweckbestimmung so, dass das "
            "System hochriskant wird, und gilt daher als dessen Anbieter.",
        },
    ),
}
"""The Art. 25(1) switches, in the order of the Act; keys are `RoleAnswer` fields."""

OWN_NAME = KeyQuestion(
    id="own_name",
    article="art:3:3",
    question={
        Language.EN: "Do you place the system on the market or put it into service under your "
        "own name or trademark?",
        Language.DE: "Bringen Sie das System unter Ihrem eigenen Namen oder Ihrer Marke in Verkehr "
        "oder nehmen Sie es so in Betrieb?",
    },
)
"""The own-brand question for a system that isn't high-risk, where Art. 25(1) doesn't apply and
the answer bears on Art. 3(3) instead (user decision on own-d-05, 2026-09-29)."""

OWN_NAME_QUESTION: Mapping[Language, str] = {
    Language.EN: "Does placing a system you didn't develop, or have developed, on the market under "
    "your own name or trademark make you its provider under Art. 3(3), which defines the provider "
    'as one that "develops … or has … developed" the system "and places it on the market … under '
    'its own name or trademark"?',
    Language.DE: "Wird man Anbieter nach Art. 3 Nr. 3, wenn man ein System, das man weder "
    "entwickelt noch entwickeln lassen hat, unter eigenem Namen oder eigener Marke in Verkehr "
    'bringt? Art. 3 Nr. 3 nennt als Anbieter, wer ein System "entwickelt oder entwickeln lässt und '
    'es unter ihrem eigenen Namen oder ihrer Handelsmarke in Verkehr bringt".',
}
OWN_NAME_READINGS: Mapping[Language, tuple[str, str]] = {
    Language.EN: (
        "Provider: it places the system on the Union market under its own name; the Commission's "
        "Art. 50 guidelines treat a company that offers an application under its own name as its "
        "provider.",
        "{base}: Art. 3(3) also needs the system to be developed by or for it, so the developer "
        "stays the provider.",
    ),
    Language.DE: (
        "Anbieter: Es bringt das System unter eigenem Namen in der Union in Verkehr; die "
        "Art.-50-Leitlinien der Kommission behandeln ein Unternehmen, das eine Anwendung unter "
        "eigenem Namen anbietet, als deren Anbieter.",
        "{base}: Art. 3 Nr. 3 verlangt auch, dass das System von ihm oder für es entwickelt wurde; "
        "Anbieter bleibt der Entwickler.",
    ),
}
"""The two readings, the stricter (provider) first; `{base}` is the base role's name."""

ROLE_NAMES: Mapping[Language, Mapping[Role, str]] = {
    Language.EN: {role: role.value for role in Role},
    Language.DE: {
        Role.PROVIDER: "Anbieter",
        Role.DEPLOYER: "Betreiber",
        Role.IMPORTER: "Einführer",
        Role.DISTRIBUTOR: "Händler",
    },
}
TEXTS: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "role": "Role: {role}.",
        "role_also": "Role: {role}, and also {also}.",
        "ambiguous": "Legally ambiguous: the system isn't high-risk, so Art. 25(1) doesn't settle "
        "the role, and it is open whether placing a system you didn't develop under your own name "
        "makes you its provider under Art. 3(3); the Commission's Art. 50 guidelines point to "
        "provider. Working assumption: provider, keeping the {base} duties.",
        "assumption_also": "Working assumption: also {also}, pending an answer to: {question}",
        "assumption": "Working assumption: provider, keeping the other role's duties, pending an "
        "answer to: {question}",
        "duties": "{count} duties listed for a {risk_class} system ({version} text).",
        "condition_not_met": "{count} conditional duties left out because their condition "
        "doesn't apply.",
        "not_found": "{count} duties left out because no earlier check reported the finding they "
        "depend on.",
        "no_table": "No duties listed: the obligations table covers only the {version} text, "
        "not the {asked} text.",
    },
    Language.DE: {
        "role": "Rolle: {role}.",
        "role_also": "Rolle: {role}, zugleich {also}.",
        "ambiguous": "Rechtlich offen: Das System ist nicht hochriskant, daher klärt Art. 25 "
        "Abs. 1 die Rolle nicht, und es ist offen, ob man mit dem Inverkehrbringen eines nicht "
        "selbst entwickelten Systems unter eigenem Namen dessen Anbieter nach Art. 3 Nr. 3 wird; "
        "die Art.-50-Leitlinien der Kommission sprechen für Anbieter. Arbeitsannahme: Anbieter, "
        "mit den Pflichten als {base}.",
        "assumption_also": "Arbeitsannahme: zugleich {also}, bis diese Frage beantwortet ist: "
        "{question}",
        "assumption": "Arbeitsannahme: Anbieter, mit den Pflichten der anderen Rolle, bis diese "
        "Frage beantwortet ist: {question}",
        "duties": "{count} Pflichten für ein System der Klasse {risk_class} ({version} Fassung).",
        "condition_not_met": "{count} bedingte Pflichten entfallen, weil ihre Bedingung nicht "
        "erfüllt ist.",
        "not_found": "{count} Pflichten entfallen, weil keine frühere Prüfung den Befund gemeldet "
        "hat, von dem sie abhängen.",
        "no_table": "Keine Pflichten aufgeführt: Die Pflichtentabelle deckt nur die "
        "{version} Fassung ab, nicht die {asked} Fassung.",
    },
}
