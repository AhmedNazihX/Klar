"""The fixed texts of the role and obligations node (E7): the deciding key facts with their
stable follow-up ids and the articles they rest on, role names, and the decision sentences, in
English and German."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from aiact.dates import long_date
from aiact.engine.nodes.reading_side import ReadingSide
from aiact.llm.replies import OpenQuestion
from aiact.schemas import Language, Role


@dataclass(frozen=True)
class KeyQuestion:
    """A deciding fact: its follow-up question and, when a "yes" makes a provider, why."""

    id: str
    article: str
    question: Mapping[Language, str]
    reason: Mapping[Language, str] | None = None
    is_yes_no: bool = True
    """Answered yes or no; False for a question answered in words (E12: no answer options)."""
    is_provider_switch: bool = False
    """A yes may make the company the provider (Art. 3(3), 25(1)); its hint says so (E12)."""


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
    is_yes_no=False,
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
    is_provider_switch=True,
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
        is_provider_switch=True,
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
        is_provider_switch=True,
        is_yes_no=False,
        question={
            Language.EN: "Have you changed the system beyond what its provider's documentation "
            "foresees, for example by retraining it for new tasks, adding inputs or changing how "
            "it decides? If so, what did you change, and what does the documentation say about "
            "such changes?",
            Language.DE: "Haben Sie das System über das hinaus verändert, was die Unterlagen "
            "seines Anbieters vorsehen, zum Beispiel für neue Aufgaben neu trainiert, Eingaben "
            "ergänzt oder seine Entscheidungslogik geändert? Wenn ja: Was haben Sie geändert, "
            "und was sagen die Unterlagen zu solchen Änderungen?",
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
        is_provider_switch=True,
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
    is_provider_switch=True,
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

SUBSTANTIAL_MODIFICATION_QUESTION: Mapping[Language, str] = {
    Language.EN: "Is the change a substantial modification under Art. 3(23), which makes you the "
    'provider under Art. 25(1)(b)? Art. 3(23) defines it as "a change to an AI system after its '
    "placing on the market or putting into service which is not foreseen or planned in the "
    "initial conformity assessment carried out by the provider and as a result of which the "
    "compliance of the AI system with the requirements set out in Chapter III, Section 2 is "
    "affected or results in a modification to the intended purpose for which the AI system has "
    'been assessed".',
    Language.DE: "Ist die Änderung eine wesentliche Veränderung nach Art. 3 Nr. 23, durch die Sie "
    "nach Art. 25 Abs. 1 Buchst. b Anbieter werden? Art. 3 Nr. 23 definiert sie als „eine "
    "Veränderung eines KI-Systems nach dessen Inverkehrbringen oder Inbetriebnahme, die in der vom "
    "Anbieter durchgeführten ursprünglichen Konformitätsbewertung nicht vorgesehen oder geplant "
    "war und durch die die Konformität des KI-Systems mit den Anforderungen in Kapitel III "
    "Abschnitt 2 beeinträchtigt wird oder die zu einer Änderung der Zweckbestimmung führt, für die "
    "das KI-System bewertet wurde“.",
}
SUBSTANTIAL_MODIFICATION_READINGS: Mapping[Language, tuple[str, str]] = {
    Language.EN: (
        "Provider: the change wasn't foreseen in the provider's conformity assessment and may "
        "affect how the system meets the high-risk requirements, so it is a substantial "
        "modification and Art. 25(1)(b) makes the company its provider.",
        "{base}: without evidence that the change affects compliance with the high-risk "
        "requirements or the intended purpose, it is no substantial modification, so the vendor "
        "stays the provider.",
    ),
    Language.DE: (
        "Anbieter: Die Änderung war in der Konformitätsbewertung des Anbieters nicht vorgesehen "
        "und kann die Erfüllung der Hochrisiko-Anforderungen berühren; sie ist daher eine "
        "wesentliche Veränderung, und nach Art. 25 Abs. 1 Buchst. b wird das Unternehmen "
        "Anbieter.",
        "{base}: Solange nicht feststeht, dass die Änderung die Erfüllung der "
        "Hochrisiko-Anforderungen oder die Zweckbestimmung berührt, ist sie keine wesentliche "
        "Veränderung; Anbieter bleibt der Hersteller.",
    ),
}
"""The two readings of an open Art. 3(23) question, the stricter (provider) first; `{base}` is
the base role's name (user decision on own-d-12, 2026-10-06)."""


@dataclass(frozen=True)
class OpenInLaw:
    """A role question the law leaves open, with the facts known: the question, both readings
    (stricter first, `{base}` in the lenient one), the decision sentence (a `TEXTS` key) and
    the provisions it rests on."""

    question: Mapping[Language, str]
    readings: Mapping[Language, tuple[str, str]]
    sentence: str
    articles: tuple[str, ...]


OWN_NAME_OPEN = OpenInLaw(
    question=OWN_NAME_QUESTION,
    readings=OWN_NAME_READINGS,
    sentence="ambiguous",
    articles=("art:3:3",),
)
"""Own name on a system that isn't high-risk: Art. 3(3) doesn't settle the role (own-d-05)."""
SUBSTANTIAL_MODIFICATION_OPEN = OpenInLaw(
    question=SUBSTANTIAL_MODIFICATION_QUESTION,
    readings=SUBSTANTIAL_MODIFICATION_READINGS,
    sentence="ambiguous_modification",
    articles=("art:25:1:b", "art:3:23"),
)
"""A change to a high-risk system whose description says what was changed and what the
provider's documentation foresees, where Art. 3(23) doesn't settle whether it is substantial
(user decision on own-d-12, 2026-10-06)."""

PERSON_REVIEW = KeyQuestion(
    id="role_person_review",
    article="art:3:3",
    is_yes_no=False,
    question={
        Language.EN: "Please have a person review the description: does your company develop the "
        "system, use a system someone else provides, import it or distribute it, and has it put "
        "its own name on it, changed it or used it for a new purpose (Art. 3, 25)?",
        Language.DE: "Bitte lassen Sie die Beschreibung von einem Menschen prüfen: Entwickelt Ihr "
        "Unternehmen das System, nutzt es ein System eines anderen Anbieters, führt es das System "
        "in die EU ein oder ist es Händler des Systems? Hat es das System unter eigenem Namen "
        "angeboten, verändert oder für einen neuen Zweck eingesetzt (Art. 3, 25)?",
    },
)
"""The question a refused reply asks (decision 029)."""


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
        Language.EN: "Is a significant change to the system's design or intended purpose "
        "planned or foreseen for on or after {date}?",
        Language.DE: "Ist ab dem {date} eine erhebliche Veränderung der Konzeption oder der "
        "Zweckbestimmung des Systems geplant oder vorgesehen?",
    },
    "for_public_authority": {
        Language.EN: "Is the system meant for use by public authorities?",
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
READING_SIDES: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "provider": "Provider",
        "provider_consequence": "If this holds, the company has the provider's duties.",
        "base_consequence": "If this holds, the company keeps the {base} role and its duties.",
    },
    Language.DE: {
        "provider": "Anbieter",
        "provider_consequence": "Gilt diese Lesart, treffen das Unternehmen die Pflichten des "
        "Anbieters.",
        "base_consequence": "Gilt diese Lesart, behält das Unternehmen die Rolle {base} und "
        "deren Pflichten.",
    },
}
"""Each reading's title and consequence (E12): the stricter reading is provider, the lenient
one the base role; neither changes the class."""


def open_in_law_parts(
    open_in_law: OpenInLaw, base: Role, language: Language
) -> tuple[OpenQuestion, ReadingSide, ReadingSide]:
    """The question with its two plain readings (stricter first, the lenient one naming the
    `base` role), then what the step knows of each: the stricter (provider) one quotes the first
    of the question's articles (the switch), the lenient one the last (the definition it turns
    on); neither changes the class."""
    words, name = READING_SIDES[language], ROLE_NAMES[language][base]
    title = name[:1].upper() + name[1:]
    stricter, lenient = open_in_law.readings[language]
    plain = OpenQuestion(
        question=open_in_law.question[language], readings=(stricter, lenient.format(base=title))
    )
    articles = open_in_law.articles
    provider = ReadingSide(words["provider"], words["provider_consequence"], None, articles[0])
    kept = ReadingSide(title, words["base_consequence"].format(base=name), None, articles[-1])
    return plain, provider, kept


TEXTS: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "role": "Role: {role}.",
        "role_also": "Role: {role}, and also {also}.",
        "ambiguous": "Legally ambiguous: the system isn't high-risk, so Art. 25(1) doesn't settle "
        "the role, and it is open whether placing a system you didn't develop under your own name "
        "makes you its provider under Art. 3(3); the Commission's Art. 50 guidelines point to "
        "provider. Working assumption: provider, keeping the {base} duties.",
        "ambiguous_modification": "Legally ambiguous: the description says what was changed and "
        "what the provider's documentation foresees, but the law doesn't settle whether the "
        "change is a substantial modification (Art. 3(23)) that makes the company the provider "
        "under Art. 25(1)(b). Working assumption: provider, keeping the {base} duties.",
        "section_b": "No AI Act duties listed: the system is high-risk as a product, or a safety "
        "component of one, under Annex I Section B, so Art. 2(2) applies only a few provisions of "
        "the AI Act to it, none of them a duty of this role; its requirements come from the "
        "sector law.",
        "section_b_possible": "If the system is high-risk as a product, or a safety component of "
        "one, under Annex I Section B, Art. 2(2) applies only a few provisions of the AI Act to "
        "it, none of them a duty of this role, and its requirements come from the sector law; "
        "until the high-risk check is settled, the duties stay listed.",
        "refusal": "Working assumption until a person has reviewed it: provider, keeping the "
        "deployer duties.",
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
        "not_modelled": "Duties not modelled for the {asked} text: the obligations table covers "
        "only the {version} text, so no duties are listed.",
        "legacy_unchanged": "Art. 111(2): the system was on the market or in use before {date}, "
        "so {count} high-risk duties apply only if its design or intended purpose changes "
        "significantly on or after that date (a substantial modification); the class stays "
        "high-risk.",
        "legacy_public_authority": "Art. 111(2): the system was on the market or in use before "
        "{date} and is meant for public authorities, so {count} high-risk duties "
        "apply from {deadline}; the class stays high-risk.",
        "legacy_public_authority_assumed": "Art. 111(2): the system was on the market or in use "
        "before {date}; until it is confirmed whether public authorities are meant to use it, the "
        "earlier date is assumed, so {count} high-risk duties apply from {deadline}; the class "
        "stays high-risk.",
        "legacy_per_product": "This covers copies placed on the market or put into service before "
        "{date}; copies supplied on or after that date may be fully covered.",
        "legacy_check_at_launch": "If the system is placed on the market or put into service "
        "before {date} and its design or intended purpose doesn't change significantly "
        "afterwards, Art. 111(2) may limit these duties; check again at launch.",
    },
    Language.DE: {
        "role": "Rolle: {role}.",
        "role_also": "Rolle: {role}, zugleich {also}.",
        "ambiguous": "Rechtlich offen: Das System ist nicht hochriskant, daher klärt Art. 25 "
        "Abs. 1 die Rolle nicht, und es ist offen, ob man mit dem Inverkehrbringen eines nicht "
        "selbst entwickelten Systems unter eigenem Namen dessen Anbieter nach Art. 3 Nr. 3 wird; "
        "die Art.-50-Leitlinien der Kommission sprechen für Anbieter. Arbeitsannahme: Anbieter, "
        "mit den Pflichten als {base}.",
        "ambiguous_modification": "Rechtlich offen: Die Beschreibung nennt die Änderung und was "
        "die Unterlagen des Anbieters vorsehen, aber das Recht klärt nicht, ob die Änderung eine "
        "wesentliche Veränderung (Art. 3 Nr. 23) ist, durch die das Unternehmen nach Art. 25 "
        "Abs. 1 Buchst. b Anbieter wird. Arbeitsannahme: Anbieter, mit den Pflichten als {base}.",
        "section_b": "Keine Pflichten aus der KI-Verordnung aufgeführt: Das System ist als Produkt "
        "oder Sicherheitsbauteil eines Produkts nach Anhang I Abschnitt B hochriskant, daher "
        "gelten nach Art. 2 Abs. 2 nur wenige Vorschriften der KI-Verordnung, keine davon eine "
        "Pflicht dieser Rolle; seine Anforderungen ergeben sich aus dem Sektorrecht.",
        "section_b_possible": "Ist das System als Produkt oder Sicherheitsbauteil eines Produkts "
        "nach Anhang I Abschnitt B hochriskant, gelten nach Art. 2 Abs. 2 nur wenige Vorschriften "
        "der KI-Verordnung, keine davon eine Pflicht dieser Rolle, und seine Anforderungen "
        "ergeben sich aus dem Sektorrecht; solange die Hochrisiko-Prüfung offen ist, bleiben die "
        "Pflichten aufgeführt.",
        "refusal": "Arbeitsannahme, bis ein Mensch sie geprüft hat: Anbieter, mit den Pflichten "
        "als Betreiber.",
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
        "not_modelled": "Pflichten für die {asked} Fassung nicht modelliert: Die "
        "Pflichtentabelle deckt nur die {version} Fassung ab, daher sind keine Pflichten "
        "aufgeführt.",
        "legacy_unchanged": "Art. 111 Abs. 2: Das System war vor dem {date} in Verkehr oder in "
        "Betrieb; daher gelten {count} Hochrisiko-Pflichten nur, wenn seine Konzeption oder "
        "Zweckbestimmung ab diesem Datum erheblich verändert wird (eine wesentliche Veränderung). "
        "Das System bleibt als Hochrisiko-System eingestuft.",
        "legacy_public_authority": "Art. 111 Abs. 2: Das System war vor dem {date} in Verkehr "
        "oder in Betrieb und soll bestimmungsgemäß von Behörden verwendet werden; daher gelten "
        "{count} Hochrisiko-Pflichten ab dem {deadline}. Das System bleibt als Hochrisiko-System "
        "eingestuft.",
        "legacy_public_authority_assumed": "Art. 111 Abs. 2: Das System war vor dem {date} in "
        "Verkehr oder in Betrieb; solange nicht geklärt ist, ob Behörden es verwenden sollen, wird "
        "das frühere Datum angenommen; daher gelten {count} Hochrisiko-Pflichten ab dem "
        "{deadline}. Das System bleibt als Hochrisiko-System eingestuft.",
        "legacy_per_product": "Dies gilt für Exemplare, die vor dem {date} in Verkehr gebracht "
        "oder in Betrieb genommen wurden; ab diesem Datum bereitgestellte Exemplare können "
        "vollständig erfasst sein.",
        "legacy_check_at_launch": "Wird das System vor dem {date} in Verkehr gebracht oder in "
        "Betrieb genommen und danach in seiner Konzeption oder Zweckbestimmung nicht erheblich "
        "verändert, kann Art. 111 Abs. 2 diese Pflichten einschränken; prüfen Sie dies beim "
        "Inverkehrbringen oder bei der Inbetriebnahme erneut.",
    },
}
