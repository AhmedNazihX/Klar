"""The fixed texts of the role and obligations node (E7): the deciding key facts with their
stable follow-up ids and the articles they rest on, role names, and the decision sentences, in
English and German."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from aiact.dates import long_date
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

# The readings mention the Commission's Art. 50 guidelines, which the step doesn't cite yet:
# guidance citations wait on get_provision (C5) and the citation validator (E9).
OWN_NAME_QUESTION: Mapping[Language, str] = {
    Language.EN: "Does placing a system you didn't develop, or have developed, on the market under "
    "your own name or trademark make you its provider under Art. 3(3)? It defines the provider as "
    'a body "that develops an AI system … or that has an AI system … developed and places it on '
    'the market or puts the AI system into service under its own name or trademark".',
    Language.DE: "Wird man Anbieter nach Art. 3 Nr. 3, wenn man ein System, das man weder "
    "entwickelt noch hat entwickeln lassen, unter eigenem Namen oder eigener Marke in Verkehr "
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


@dataclass(frozen=True)
class LegacyQuestions:
    """The Art. 111(2) key facts for one route, their questions naming its Chapter III date."""

    placed_before: KeyQuestion
    design_change: KeyQuestion
    public_authority: KeyQuestion


LEGACY_QUESTION_TEXTS: Mapping[str, Mapping[Language, str]] = {
    "placed_before_chapter_iii": {
        Language.EN: "Is the system already on the market or in use today? Its high-risk rules "
        "apply from {date}.",
        Language.DE: "Ist das System heute bereits auf dem Markt oder in Betrieb? Seine "
        "Hochrisiko-Vorschriften gelten ab dem {date}.",
    },
    "significant_design_change": {
        Language.EN: "Has the system's design changed significantly since it was placed on the "
        "market or put into service, or is a significant change planned for after {date} (for "
        "example a new version that decides differently or serves another purpose)?",
        Language.DE: "Wurde die Konzeption des Systems seit dem Inverkehrbringen oder der "
        "Inbetriebnahme erheblich verändert, oder ist nach dem {date} eine erhebliche "
        "Veränderung geplant (zum Beispiel eine neue Version, die anders entscheidet oder einem "
        "anderen Zweck dient)?",
    },
    "for_public_authority": {
        Language.EN: "Will public authorities use the system, as it is meant to be used?",
        Language.DE: "Soll das System bestimmungsgemäß von Behörden verwendet werden?",
    },
}
"""The Art. 111(2) questions, by follow-up id; `{date}` is the route's Chapter III date."""


def legacy_questions(chapter_iii_from: date, article: str) -> LegacyQuestions:
    """The Art. 111(2) questions for a route whose high-risk rules apply from `chapter_iii_from`."""

    def key(question_id: str) -> KeyQuestion:
        texts = LEGACY_QUESTION_TEXTS[question_id]
        question = {
            language: text.format(date=long_date(chapter_iii_from, language))
            for language, text in texts.items()
        }
        return KeyQuestion(id=question_id, article=article, question=question)

    return LegacyQuestions(
        placed_before=key("placed_before_chapter_iii"),
        design_change=key("significant_design_change"),
        public_authority=key("for_public_authority"),
    )


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
        "still_asked": "Still to confirm: {question}",
        "assumption_own_name": "Working assumption: provider, keeping the {base} duties. If you "
        "do place it under your own name, whether that makes you its provider is legally open "
        "(Art. 3(3)); if not, you stay a {base}. Please answer: {question}",
        "duties": "{count} duties listed for a {risk_class} system ({version} text).",
        "condition_not_met": "{count} conditional duties left out because their condition "
        "doesn't apply.",
        "not_found": "{count} duties left out because no earlier check reported the finding they "
        "depend on.",
        "no_table": "No duties listed: the obligations table covers only the {version} text, "
        "not the {asked} text.",
        "legacy_unchanged": "Art. 111(2): the system was on the market or in use before {date} "
        "and its design hasn't changed significantly since, so {count} high-risk duties apply "
        "only after a significant design change; the class stays high-risk.",
        "legacy_public_authority": "Art. 111(2): the system was on the market or in use before "
        "{date} and is meant for public authorities, so {count} high-risk duties "
        "apply from {deadline}; the class stays high-risk.",
        "legacy_check_at_launch": "If the system is placed on the market or put into service "
        "before {date} and its design doesn't change significantly afterwards, Art. 111(2) may "
        "limit these duties; check again at launch.",
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
        "still_asked": "Noch zu bestätigen: {question}",
        "assumption_own_name": "Arbeitsannahme: Anbieter, mit den Pflichten als {base}. Bringen "
        "Sie es unter eigenem Namen in Verkehr, ist rechtlich offen, ob Sie damit Anbieter werden "
        "(Art. 3 Nr. 3); wenn nicht, bleiben Sie {base}. Bitte beantworten Sie: {question}",
        "duties": "{count} Pflichten für ein System der Klasse {risk_class} ({version} Fassung).",
        "condition_not_met": "{count} bedingte Pflichten entfallen, weil ihre Bedingung nicht "
        "erfüllt ist.",
        "not_found": "{count} Pflichten entfallen, weil keine frühere Prüfung den Befund gemeldet "
        "hat, von dem sie abhängen.",
        "no_table": "Keine Pflichten aufgeführt: Die Pflichtentabelle deckt nur die "
        "{version} Fassung ab, nicht die {asked} Fassung.",
        "legacy_unchanged": "Art. 111 Abs. 2: Das System war vor dem {date} in Verkehr oder in "
        "Betrieb und wurde seitdem nicht erheblich in seiner Konzeption verändert; daher gelten "
        "{count} Hochrisiko-Pflichten erst nach einer erheblichen Veränderung der Konzeption. Die "
        "Klasse bleibt hochriskant.",
        "legacy_public_authority": "Art. 111 Abs. 2: Das System war vor dem {date} in Verkehr "
        "oder in Betrieb und soll bestimmungsgemäß von Behörden verwendet werden; daher gelten "
        "{count} Hochrisiko-Pflichten ab dem {deadline}. Die Klasse bleibt hochriskant.",
        "legacy_check_at_launch": "Wird das System vor dem {date} in Verkehr gebracht oder in "
        "Betrieb genommen und danach in seiner Konzeption nicht erheblich verändert, kann Art. 111 "
        "Abs. 2 diese Pflichten einschränken; prüfen Sie es beim Markteintritt erneut.",
    },
}
