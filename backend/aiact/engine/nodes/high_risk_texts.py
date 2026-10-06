"""The fixed texts of the high-risk node (E5): the deciding key facts with their stable follow-up
ids and the provisions they rest on, how Annex points are named, and the decision sentences, in
English and German. `{law}` is the Annex I legislation's short title, from the corpus."""

import re
from collections.abc import Mapping

from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.retrieval.provisions import Provision
from aiact.schemas import Language

EN, DE = Language.EN, Language.DE

# --- Annex I (Art. 6(1)) ------------------------------------------------------------------------

INTENDED_PURPOSE = KeyQuestion(
    id="intended_purpose",
    article="art:6:1:a",
    question={
        EN: "Will the product be placed on the market or put into service with an intended "
        "purpose that brings it under {law}?",
        DE: "Wird das Produkt mit einer Zweckbestimmung in Verkehr gebracht oder in Betrieb "
        "genommen, die es unter {law} fallen lässt?",
    },
)
SAFETY_COMPONENT = KeyQuestion(
    id="safety_component",
    article="art:6:1:a",
    question={
        EN: "Does the AI system perform a safety function for the product covered by {law}, or "
        "could its failure or malfunction endanger the health or safety of people?",
        DE: "Erfüllt das KI-System eine Sicherheitsfunktion für das Produkt, das unter {law} "
        "fällt, oder könnte sein Ausfall oder seine Störung die Gesundheit oder Sicherheit von "
        "Menschen gefährden?",
    },
)
THIRD_PARTY_ASSESSMENT = KeyQuestion(
    id="third_party_assessment",
    article="art:6:1:b",
    question={
        EN: "Under {law}, must the product undergo a third-party conformity assessment (for "
        "example by a notified body) for health and safety before it is placed on the market or "
        "put into service?",
        DE: "Muss das Produkt nach {law} vor dem Inverkehrbringen oder der Inbetriebnahme eine "
        "Konformitätsbewertung durch Dritte (zum Beispiel eine benannte Stelle) zu Gesundheit und "
        "Sicherheit durchlaufen?",
    },
)
ANNEX_I_QUESTIONS = (INTENDED_PURPOSE, SAFETY_COMPONENT, THIRD_PARTY_ASSESSMENT)
"""In the order Art. 6(1) asks them: covered by the law, safety component, third-party check."""

# --- Annex III (Art. 6(2)) and the Art. 6(3) filter ---------------------------------------------

PROFILING = KeyQuestion(
    id="profiling",
    article="art:6:3",
    question={
        EN: "Does the system profile people, that is, use their personal data to evaluate or "
        "predict personal aspects such as their work, economic situation, health, reliability "
        "or behaviour?",
        DE: "Erstellt das System Profile von Personen, bewertet oder prognostiziert es also "
        "anhand ihrer personenbezogenen Daten persönliche Aspekte wie Arbeitsleistung, "
        "wirtschaftliche Lage, Gesundheit, Zuverlässigkeit oder Verhalten?",
    },
)
PUBLIC_SCHEME = KeyQuestion(
    id="public_scheme",
    article="annex:III:5:a",
    is_yes_no=False,
    question={
        EN: "Is the benefits or services scheme run by a public authority or on its behalf, or "
        "is it a private scheme?",
        DE: "Wird das Leistungs- oder Versorgungsprogramm von einer Behörde oder in ihrem Auftrag "
        "betrieben, oder ist es ein privates Programm?",
    },
)
DECIDES_ADMISSION = KeyQuestion(
    id="decides_admission",
    article="annex:III:3:a",
    is_yes_no=False,
    question={
        EN: "Does the decision determine whether a person is admitted to, or assigned to, an "
        "education or training institution, or does it only fund people who are already "
        "admitted?",
        DE: "Entscheidet das Ergebnis darüber, ob eine Person an einer Bildungs- oder "
        "Ausbildungseinrichtung zugelassen oder ihr zugewiesen wird, oder werden damit nur "
        "bereits zugelassene Personen gefördert?",
    },
)
JUDICIAL_USE = KeyQuestion(
    id="judicial_use",
    article="annex:III:8:a",
    question={
        EN: "Is the system used by a judicial authority or on its behalf, or in alternative "
        "dispute resolution?",
        DE: "Wird das System von einer Justizbehörde oder in ihrem Auftrag oder in der "
        "alternativen Streitbeilegung eingesetzt?",
    },
)
PUBLIC_AUTHORITY_USER = KeyQuestion(
    id="public_authority_user",
    article="annex:III:7",
    question={
        EN: "Please confirm: the system is used by or on behalf of a competent public authority.",
        DE: "Bitte bestätigen Sie: Das System wird von einer zuständigen Behörde oder in ihrem "
        "Auftrag eingesetzt.",
    },
)
"""Asked for Annex III 6 and 7; the node sets `article` to the area matched."""
ANNEX_III_USE = KeyQuestion(
    id="annex_iii_use",
    article="art:6:2",
    is_yes_no=False,
    question={
        EN: "What exactly is the system's output used for, and who relies on it?",
        DE: "Wofür genau wird das Ergebnis des Systems verwendet, und wer stützt sich darauf?",
    },
)
"""The fallback when the model leaves a point open but names no question of its own."""

AUTHORITY_ASSUMED: Mapping[Language, str] = {
    EN: "Used by or on behalf of a competent public authority.",
    DE: "Wird von einer zuständigen Behörde oder in ihrem Auftrag eingesetzt.",
}
"""The fact assumed for an Annex III 6 or 7 use when the description doesn't name the user."""

# --- A provider refusal (decision 029) -----------------------------------------------------------

PERSON_REVIEW = KeyQuestion(
    id="high_risk_person_review",
    article="art:6",
    is_yes_no=False,
    question={
        EN: "Please have a person review the description: is the system used for a purpose "
        "listed in Annex III, or is it a product, or a safety component of a product, covered by "
        "the EU law listed in Annex I (Art. 6)?",
        DE: "Bitte lassen Sie die Beschreibung von einem Menschen prüfen: Wird das System für "
        "einen in Anhang III genannten Zweck eingesetzt, oder ist es ein Produkt oder ein "
        "Sicherheitsbauteil eines Produkts, das unter die in Anhang I genannten "
        "EU-Rechtsvorschriften fällt (Art. 6)?",
    },
)
REFUSAL: Mapping[Language, str] = {
    EN: "Until a person has reviewed it, the system is assumed to be high-risk, and the Annex III "
    "requirements are assumed.",
    DE: "Bis ein Mensch sie geprüft hat, wird angenommen, dass das System hochriskant ist, und es "
    "werden die Anforderungen nach Anhang III angenommen.",
}
"""The refusal step's assumption, after the shared first sentence (`common.BLOCKED`): high-risk
on the Annex III route, whose dates come first."""
REFUSAL_CITATIONS = ("art:6:1", "art:6:2")
"""What the refusal step cites: the two routes to high-risk."""

# --- Decision sentences -------------------------------------------------------------------------

TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "iii_high": "High-risk: the system is used as listed in {point} (Art. 6(2)).",
        "iii_profiling": "It profiles natural persons, so the Art. 6(3) exemption cannot apply.",
        "iii_no_condition": "None of the Art. 6(3) conditions applies, so it is not exempt.",
        "iii_exempt": "Not high-risk: the system is used as listed in {point}, but it meets "
        "Art. 6(3)({condition}) and does not profile people, so it is exempt. The provider must "
        "document this assessment before placing it on the market and register it "
        "(Art. 6(4), 49(2)).",
        "i_high": "High-risk under Art. 6(1): the AI system is a safety component of a product "
        "covered by {law} ({point}), or is itself such a product, and the product needs a "
        "third-party conformity assessment.",
        "i_section_b": "{law} is listed in Annex I Section B, so under Art. 2(2) only Art. 6(1), "
        "Art. 60a and Art. 102 to 112 of the AI Act apply: the high-risk requirements reach the "
        "product through {law}, and the AI Act itself imposes no further obligations.",
        "i_not_covered": "The product is not covered by {law} ({point}), so Art. 6(1) does not "
        "apply.",
        "i_not_safety": "The AI system is not a safety component of the product covered by {law} "
        "({point}) (Art. 6(1)(a), 6(1a)), so Art. 6(1) does not apply.",
        "i_no_third_party": "The product covered by {law} ({point}) does not need a third-party "
        "conformity assessment for health and safety (Art. 6(1)(b), 6(1c)), so Art. 6(1) does not "
        "apply.",
        "none": "Not high-risk: no Annex III use was found, and the system is not a safety "
        "component of a product under Annex I that needs a third-party conformity assessment.",
        "assumed": "Assumed high-risk on the {route} route until this is answered: {question}",
        "assumed_exempt": "Assumed exempt under Art. 6(3) until this is answered: {question}",
        "ambiguous": "Assumed high-risk on the {route} route pending legal review: {question}",
        "examples": "Compared with the guideline examples {ids}.",
    },
    DE: {
        "iii_high": "Hochrisiko: Das System wird wie in {point} aufgeführt eingesetzt "
        "(Art. 6 Abs. 2).",
        "iii_profiling": "Es erstellt Profile natürlicher Personen, daher kann die Ausnahme nach "
        "Art. 6 Abs. 3 nicht greifen.",
        "iii_no_condition": "Keine der Bedingungen des Art. 6 Abs. 3 ist erfüllt, daher greift "
        "keine Ausnahme.",
        "iii_exempt": "Kein Hochrisiko: Das System wird wie in {point} aufgeführt eingesetzt, "
        "erfüllt aber Art. 6 Abs. 3 Buchst. {condition} und erstellt keine Profile von Personen, "
        "daher greift die Ausnahme. Der Anbieter muss diese Bewertung vor dem Inverkehrbringen "
        "dokumentieren und das System registrieren (Art. 6 Abs. 4, Art. 49 Abs. 2).",
        "i_high": "Hochrisiko nach Art. 6 Abs. 1: Das KI-System ist ein Sicherheitsbauteil eines "
        "Produkts, das unter {law} fällt ({point}), oder selbst ein solches Produkt, und das "
        "Produkt muss eine Konformitätsbewertung durch Dritte durchlaufen.",
        "i_section_b": "{law} ist in Anhang I Abschnitt B aufgeführt, daher gelten nach "
        "Art. 2 Abs. 2 von der KI-Verordnung nur Art. 6 Abs. 1, Art. 60a und Art. 102 bis 112: "
        "Die Hochrisiko-Anforderungen erreichen das Produkt über {law}, die KI-Verordnung selbst "
        "legt keine weiteren Pflichten auf.",
        "i_not_covered": "Das Produkt fällt nicht unter {law} ({point}), daher gilt Art. 6 "
        "Abs. 1 nicht.",
        "i_not_safety": "Das KI-System ist kein Sicherheitsbauteil des Produkts, das unter {law} "
        "fällt ({point}) (Art. 6 Abs. 1 Buchst. a, Abs. 1a), daher gilt Art. 6 Abs. 1 nicht.",
        "i_no_third_party": "Das Produkt, das unter {law} fällt ({point}), muss keine "
        "Konformitätsbewertung durch Dritte zu Gesundheit und Sicherheit durchlaufen (Art. 6 "
        "Abs. 1 Buchst. b, Abs. 1c), daher gilt Art. 6 Abs. 1 nicht.",
        "none": "Kein Hochrisiko: Es wurde keine Verwendung nach Anhang III gefunden, und das "
        "System ist kein Sicherheitsbauteil eines Produkts nach Anhang I, das eine "
        "Konformitätsbewertung durch Dritte durchlaufen muss.",
        "assumed": "Bis zur Antwort auf diese Frage wird Hochrisiko über {route} angenommen: "
        "{question}",
        "assumed_exempt": "Bis zur Antwort auf diese Frage wird die Ausnahme nach Art. 6 Abs. 3 "
        "angenommen: {question}",
        "ambiguous": "Bis zur rechtlichen Prüfung wird Hochrisiko über {route} angenommen: "
        "{question}",
        "examples": "Verglichen mit den Beispielen aus den Leitlinien {ids}.",
    },
}

OPEN_FALLBACK: Mapping[Language, Mapping[str, tuple[str, str, str]]] = {
    EN: {
        "annex_iii": (
            "Do the Act and guidance settle whether the Annex III point, or the Art. 6(3) "
            "exemption, applies to this use?",
            "High-risk: the use falls under the point and is not exempt.",
            "Not high-risk: the point does not apply, or the exemption does.",
        ),
        "annex_i": (
            "Do the Act and guidance settle whether Art. 6(1) is met for this product?",
            "High-risk: Art. 6(1) is met.",
            "Not high-risk: Art. 6(1) is not met.",
        ),
    },
    DE: {
        "annex_iii": (
            "Klären Verordnung und Leitlinien, ob die Nummer aus Anhang III oder die Ausnahme "
            "nach Art. 6 Abs. 3 auf diese Verwendung zutrifft?",
            "Hochrisiko: Die Verwendung fällt unter die Nummer, und keine Ausnahme greift.",
            "Kein Hochrisiko: Die Nummer trifft nicht zu, oder die Ausnahme greift.",
        ),
        "annex_i": (
            "Klären Verordnung und Leitlinien, ob Art. 6 Abs. 1 für dieses Produkt erfüllt ist?",
            "Hochrisiko: Art. 6 Abs. 1 ist erfüllt.",
            "Kein Hochrisiko: Art. 6 Abs. 1 ist nicht erfüllt.",
        ),
    },
}
"""The open question and its two readings (stricter first) when the model marks a route
unsettled in law without stating the question: `(question, stricter, lenient)`."""

ROUTE_NAMES: Mapping[Language, Mapping[str, str]] = {
    EN: {"annex_iii": "Annex III", "annex_i": "Annex I"},
    DE: {"annex_iii": "Anhang III", "annex_i": "Anhang I"},
}

# --- The readings of an open question (E12) ----------------------------------------------------

READINGS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "high_iii": "High-risk under {point}",
        "high_i": "High-risk under Art. 6(1)",
        "not_iii": "Not covered by {point}",
        "not_i": "Art. 6(1) not met",
        "exempt": "Exempt under Art. 6(3)",
        "high_consequence": "If this holds, the high-risk duties apply from {date}.",
        "section_b_consequence": "If this holds, the high-risk requirements reach the product "
        "through {law}; the AI Act itself adds no duties (Art. 2(2)).",
        "not_high_consequence": "If this holds, the system is not high-risk on this point. The "
        "transparency check then decides whether any duties apply.",
        "exempt_consequence": "If this holds, the provider must document why the system is not "
        "high-risk before placing it on the market, and register it (Art. 6(4), 49(2)).",
    },
    DE: {
        "high_iii": "Hochrisiko nach {point}",
        "high_i": "Hochrisiko nach Art. 6 Abs. 1",
        "not_iii": "Nicht von {point} erfasst",
        "not_i": "Art. 6 Abs. 1 nicht erfüllt",
        "exempt": "Ausnahme nach Art. 6 Abs. 3",
        "high_consequence": "Gilt diese Lesart, gelten die Hochrisiko-Pflichten ab dem {date}.",
        "section_b_consequence": "Gilt diese Lesart, erreichen die Hochrisiko-Anforderungen das "
        "Produkt über {law}; die KI-Verordnung selbst legt keine Pflichten auf (Art. 2 Abs. 2).",
        "not_high_consequence": "Gilt diese Lesart, ist das System in diesem Punkt nicht "
        "hochriskant. Die Transparenzprüfung entscheidet dann, ob Pflichten gelten.",
        "exempt_consequence": "Gilt diese Lesart, muss der Anbieter vor dem Inverkehrbringen "
        "dokumentieren, warum das System nicht hochriskant ist, und es registrieren (Art. 6 "
        "Abs. 4, Art. 49 Abs. 2).",
    },
}
"""Each reading's title and consequence; the stricter reading is high-risk on the route, the
lenient one is outside the point (or Art. 6(1)), or exempt when the open question is Art. 6(3).
The lenient consequence is decision 026 item 13's sentence: no class before the later checks."""

SETTLED_BY: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "guidelines": "Final Commission guidelines on high-risk classification (still a draft, "
        "{date})",
        "provider": "The provider's own Art. 6(3) assessment, documented under Art. 6(4), if it "
        "made one",
    },
    DE: {
        "guidelines": "Endgültige Leitlinien der Kommission zur Einstufung als Hochrisiko "
        "(noch ein Entwurf, {date})",
        "provider": "Die eigene Bewertung des Anbieters nach Art. 6 Abs. 3, dokumentiert nach "
        "Art. 6 Abs. 4, falls er eine vorgenommen hat",
    },
}
"""What would settle an open high-risk question: the final guidelines, named as the draft they
still are and never with a promise to check again (decision 026 item 4), and for an open
Art. 6(3) question the provider's own documented assessment."""


def point_name(point: str, language: Language) -> str:
    """How a result names an Annex point: `annex:III:4:a` is "Annex III point 4(a)" in English
    and "Anhang III Nummer 4 Buchstabe a" in German; `annex:I:A:11` is "Annex I Section A point
    11" or "Anhang I Abschnitt A Nummer 11"."""
    parts = point.split(":")[1:]
    if parts[0] == "I" and len(parts) == 3:
        _, section, number = parts
        if language is DE:
            return f"Anhang I Abschnitt {section} Nummer {number}"
        return f"Annex I Section {section} point {number}"
    number, letter = parts[1], parts[2] if len(parts) > 2 else None
    if language is DE:
        return f"Anhang III Nummer {number}" + (f" Buchstabe {letter}" if letter else "")
    return f"Annex III point {number}" + (f"({letter})" if letter else "")


# --- The Annex I legislation's short title -------------------------------------------------------

ACT_SHORT_TITLE = re.compile(
    r" (of the European Parliament and of the Council|des Europäischen Parlaments und des Rates)"
    r"( of| vom) \d{1,2}\.? \w+ \d{4}"
)
HARMONISATION_WORDS = re.compile(
    r"on the harmonisation of the laws of the Member States relating to "
    r"(the making available on the market of )?"
    r"|(zur Angleichung|zur Harmonisierung|über die Harmonisierung) der Rechtsvorschriften der "
    r"Mitgliedstaaten (über|für) (die Bereitstellung von )?"
)
GERMAN_ACCUSATIVE: Mapping[str, str] = {"Druckgeräten": "Druckgeräte"}
"""A noun left in the dative once "über die Bereitstellung von" is dropped from a title."""
TITLE_END = re.compile(
    r",| and repealing| und zur Aufhebung| zur Aufhebung| sowie| auf dem Markt| \(OJ| \(ABl"
)


def law_title(provision: Provision) -> str:
    """The Annex I legislation's short title: `Regulation (EU) 2017/745 on medical devices`."""
    text = re.sub(r"^\d+\.\s*", "", provision.text.strip())
    short = ACT_SHORT_TITLE.sub("", text, count=1)
    short = HARMONISATION_WORDS.sub(lambda m: "über " if m.group(2) else "on ", short, count=1)
    title = TITLE_END.split(short, maxsplit=1)[0].strip()
    for dative, accusative in GERMAN_ACCUSATIVE.items():
        title = title.replace(f"über {dative}", f"über {accusative}")
    return title
