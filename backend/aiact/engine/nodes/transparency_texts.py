"""The fixed texts of the transparency node (E6): the deciding key facts of each Art. 50 duty with
their stable follow-up ids and the provisions they rest on, how the duties are named, and the
decision sentences, in English and German."""

from collections.abc import Mapping

from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.schemas import Language

EN, DE = Language.EN, Language.DE


def _question(slug: str, article: str, en: str, de: str) -> KeyQuestion:
    return KeyQuestion(id=slug, article=article, question={EN: en, DE: de})


# --- Art. 50(1): interaction with people --------------------------------------------------------

INTERACTS_DIRECTLY = _question(
    "interacts_directly",
    "art:50:1",
    "Do people interact with the system directly, for example by chatting or talking with it?",
    "Interagieren Menschen direkt mit dem System, zum Beispiel indem sie mit ihm chatten oder "
    "sprechen?",
)
INTERACTION_OBVIOUS = _question(
    "interaction_obvious",
    "art:50:1",
    "Who uses the system, and is it obvious to them from the context that they are dealing with "
    "an AI system?",
    "Wer nutzt das System, und ist ihnen aus dem Zusammenhang offensichtlich, dass sie es mit "
    "einem KI-System zu tun haben?",
)

# --- Art. 50(2): synthetic content ---------------------------------------------------------------

GENERATES_CONTENT = _question(
    "generates_synthetic_content",
    "art:50:2",
    "Does the system itself generate audio, images, video or text, or does it only select or "
    "play back content that people made?",
    "Erzeugt das System selbst Audio, Bilder, Videos oder Texte, oder wählt es nur von Menschen "
    "erstellte Inhalte aus oder spielt sie ab?",
)
SUBSTANTIAL_ALTERATION = _question(
    "alters_substance",
    "art:50:2",
    "How far does the system change the content it is given: does it only correct or tidy it, "
    "or does it change its substance or meaning?",
    "Wie stark verändert das System die Inhalte, die es bekommt: Korrigiert oder glättet es sie "
    "nur, oder verändert es ihre Substanz oder Bedeutung?",
)

# --- Art. 50(3): emotion recognition and biometric categorisation -------------------------------

EMOTION_OR_BIOMETRIC = _question(
    "emotion_or_biometric_categorisation",
    "art:50:3",
    "Does the system recognise people's emotions or intentions, or sort people into categories "
    "from their biometric data, such as their face or voice?",
    "Erkennt das System Emotionen oder Absichten von Menschen, oder ordnet es Menschen anhand "
    "ihrer biometrischen Daten, etwa Gesicht oder Stimme, Kategorien zu?",
)

# --- Art. 50(4): deep fakes and text on matters of public interest -------------------------------

DEEP_FAKE = _question(
    "deep_fake",
    "art:50:4",
    "Does the generated image, audio or video show real-looking people, objects, places or events "
    "that could be taken for authentic?",
    "Zeigen die erzeugten Bilder, Tonaufnahmen oder Videos echt wirkende Personen, Gegenstände, "
    "Orte oder Ereignisse, die für authentisch gehalten werden könnten?",
)
PUBLIC_INTEREST_TEXT = _question(
    "public_interest_text",
    "art:50:4",
    "Is text the system generates published to inform the public on matters of public interest?",
    "Werden vom System erzeugte Texte veröffentlicht, um die Öffentlichkeit über Angelegenheiten "
    "von öffentlichem Interesse zu informieren?",
)
EDITORIAL_CONTROL = _question(
    "editorial_control",
    "art:50:4",
    "Does a person review or edit each text before it is published, and does a person or company "
    "hold editorial responsibility for the publication?",
    "Prüft oder bearbeitet ein Mensch jeden Text vor der Veröffentlichung, und trägt eine Person "
    "oder ein Unternehmen die redaktionelle Verantwortung für die Veröffentlichung?",
)

# --- Art. 50(3) and (4): the law-enforcement exception ------------------------------------------

LAW_ENFORCEMENT = _question(
    "authorised_for_law_enforcement",
    "art:50",
    "Is the system authorised by law to detect, prevent, investigate or prosecute criminal "
    "offences?",
    "Ist das System gesetzlich zur Aufdeckung, Verhütung, Ermittlung oder Verfolgung von "
    "Straftaten zugelassen?",
)

# --- Art. 111(4): the grace period for marking --------------------------------------------------

MARKET_DATE = _question(
    "first_placed_on_market",
    "art:111:4",
    "When was the system first placed on the market, or put into service, in the EU: before 2 "
    "August 2026, or later?",
    "Wann wurde das System in der EU erstmals in Verkehr gebracht oder in Betrieb genommen: vor "
    "dem 2. August 2026 oder später?",
)

# --- A provider refusal (decision 029) -----------------------------------------------------------

PERSON_REVIEW = _question(
    "transparency_person_review",
    "art:50",
    "Please have a person review the description: does the system interact directly with people, "
    "generate audio, images, video or text, recognise emotions or categorise people biometrically, "
    "or produce deep fakes (Art. 50)?",
    "Bitte lassen Sie die Beschreibung von einem Menschen prüfen: Interagiert das System direkt "
    "mit Menschen, erzeugt es Audio, Bilder, Videos oder Texte, erkennt es Emotionen, ordnet es "
    "Menschen biometrisch Kategorien zu oder erzeugt es Deepfakes (Art. 50)?",
)
REFUSAL: Mapping[Language, str] = {
    EN: "The model provider's content filter blocked this description, so it could not be "
    "assessed automatically. Every transparency duty of Art. 50(1) to (4) is assumed until a "
    "person has reviewed it.",
    DE: "Der Inhaltsfilter des Modellanbieters hat diese Beschreibung blockiert, daher konnte sie "
    "nicht automatisch geprüft werden. Bis ein Mensch sie geprüft hat, werden alle "
    "Transparenzpflichten nach Art. 50 Abs. 1 bis 4 angenommen.",
}
REFUSAL_ERROR = "provider_refusal"
"""The step's error code for a refusal."""

# --- Naming and decision sentences --------------------------------------------------------------


def provision_name(provision_id: str, language: Language) -> str:
    """How a result names an Art. 50 or Art. 111 paragraph: `art:50:1` is "Art. 50(1)" in
    English and "Art. 50 Abs. 1" in German."""
    _, article, paragraph = provision_id.split(":")
    return f"Art. {article} Abs. {paragraph}" if language is DE else f"Art. {article}({paragraph})"


TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "duties": "Transparency duties apply under {points}.",
        "none": "No transparency duty under Art. 50 applies.",
        "considered": "Considered {point}: {fact}",
        "missing": "{point} is assumed until this is answered: {question}",
        "ambiguous": "{point} is assumed pending legal review: {question}",
        "grace": "The system was placed on the market before 2 August 2026, so its outputs must "
        "be marked under Art. 50(2) by {deadline} (Art. 111(4)).",
        "grace_in_service": "The system was put into service, but not placed on the market, "
        "before 2 August 2026. Art. 111(4) gives until {deadline} only to systems placed on the "
        "market, so on the Act's wording marking under Art. 50(2) applies now; the Commission's "
        "guidelines also extend that period to systems put into service.",
        "grace_unknown": "If the system was placed on the market before 2 August 2026, its "
        "outputs must be marked under Art. 50(2) by {deadline} (Art. 111(4)); otherwise marking "
        "applies now.",
    },
    DE: {
        "duties": "Transparenzpflichten bestehen nach {points}.",
        "none": "Keine Transparenzpflicht nach Art. 50 trifft zu.",
        "considered": "Geprüft: {point}: {fact}",
        "missing": "Bis zur Antwort auf diese Frage wird {point} angenommen: {question}",
        "ambiguous": "Bis zur rechtlichen Prüfung wird {point} angenommen: {question}",
        "grace": "Das System wurde vor dem 2. August 2026 in Verkehr gebracht, daher müssen seine "
        "Ausgaben bis zum {deadline} nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 Abs. 4).",
        "grace_in_service": "Das System wurde vor dem 2. August 2026 in Betrieb genommen, aber "
        "nicht in Verkehr gebracht. Art. 111 Abs. 4 gewährt die Frist bis zum {deadline} nur "
        "Systemen, die in Verkehr gebracht wurden, daher gilt die Kennzeichnung nach Art. 50 "
        "Abs. 2 nach dem Wortlaut der Verordnung schon jetzt; die Leitlinien der Kommission "
        "erstrecken die Frist auch auf in Betrieb genommene Systeme.",
        "grace_unknown": "Wurde das System vor dem 2. August 2026 in Verkehr gebracht, müssen "
        "seine Ausgaben bis zum {deadline} nach Art. 50 Abs. 2 gekennzeichnet werden (Art. 111 "
        "Abs. 4); andernfalls gilt die Kennzeichnung schon jetzt.",
    },
}

OPEN_FALLBACK: Mapping[Language, tuple[str, str, str]] = {
    EN: (
        "Do the Act and guidance settle whether {point} applies to this system?",
        "{point} applies.",
        "{point} does not apply.",
    ),
    DE: (
        "Klären Verordnung und Leitlinien, ob {point} auf dieses System zutrifft?",
        "{point} trifft zu.",
        "{point} trifft nicht zu.",
    ),
}
"""The open question and its two readings (stricter first) when the model marks a duty unsettled
in law without stating the question: `(question, stricter, lenient)`."""
