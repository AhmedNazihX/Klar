"""The fixed texts of the prohibited node (E4): the deciding key facts of each Art. 5 practice with
their stable follow-up ids and the provisions they rest on, how the practices are named, and the
decision sentences, in English and German."""

from collections.abc import Mapping

from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.schemas import Language

EN, DE = Language.EN, Language.DE


def _question(slug: str, article: str, en: str, de: str) -> KeyQuestion:
    return KeyQuestion(id=slug, article=article, question={EN: en, DE: de})


# --- Art. 5(1)(a) and (b): manipulation and exploiting vulnerabilities --------------------------

MANIPULATIVE_TECHNIQUE = _question(
    "manipulative_technique",
    "art:5:1:a",
    "Does the system use subliminal techniques, or techniques meant to manipulate or deceive "
    "people, to steer what they decide?",
    "Setzt das System unterschwellige Techniken oder Techniken ein, die Menschen manipulieren "
    "oder täuschen sollen, um ihre Entscheidungen zu lenken?",
)
EXPLOITS_VULNERABILITY = _question(
    "exploits_vulnerability",
    "art:5:1:b",
    "Does the system take advantage of a weakness people have because of their age, a "
    "disability or their social or economic situation?",
    "Nutzt das System eine Schwäche aus, die Menschen wegen ihres Alters, einer Behinderung "
    "oder ihrer sozialen oder wirtschaftlichen Lage haben?",
)
DISTORTS_BEHAVIOUR = _question(
    "distorts_behaviour",
    "art:5:1:a",
    "Does the system noticeably impair people's ability to make an informed decision, so that "
    "they decide in a way they otherwise would not have?",
    "Beeinträchtigt das System merklich die Fähigkeit der Menschen, eine informierte "
    "Entscheidung zu treffen, sodass sie anders entscheiden, als sie es sonst getan hätten?",
)
SIGNIFICANT_HARM = _question(
    "significant_harm",
    "art:5:1:a",
    "What harm do the people affected suffer, or are likely to suffer, from those decisions: "
    "for example financial loss, damage to health or psychological harm, and how serious is it?",
    "Welcher Schaden entsteht den betroffenen Menschen durch diese Entscheidungen oder droht "
    "ihnen, etwa ein finanzieller Verlust, ein Gesundheitsschaden oder ein psychischer Schaden, "
    "und wie schwer wiegt er?",
)

# --- Art. 5(1)(ba) and (bb), with Art. 5(1a) and (1b) -------------------------------------------

INTIMATE_IMAGERY = _question(
    "intimate_imagery",
    "art:5:1:ba",
    "Can the system generate or alter realistic images, video or audio that show an "
    "identifiable real person's intimate parts or show them in sexual activity?",
    "Kann das System realistische Bilder, Videos oder Tonaufnahmen erzeugen oder verändern, die "
    "intime Körperbereiche einer erkennbaren realen Person oder sie bei sexuellen Handlungen "
    "zeigen?",
)
CHILD_ABUSE_MATERIAL = _question(
    "child_abuse_material",
    "art:5:1:bb",
    "Can the system generate or alter sexual material involving children?",
    "Kann das System sexuelles Material erzeugen oder verändern, in dem Kinder vorkommen?",
)
ONLY_CONCEALS = _question(
    "only_conceals",
    "art:5:1b",
    "Does the system only alter material in a way that shows no more of the intimate parts "
    "and does not change the sexual activity depicted, for example by hiding or blurring them?",
    "Verändert das System Material nur so, dass von den intimen Körperbereichen nicht mehr zu "
    "sehen ist und die gezeigten sexuellen Handlungen gleich bleiben, etwa durch Verdecken oder "
    "Unscharfmachen?",
)
CONSENT = _question(
    "consent",
    "art:5:1:ba",
    "Has every person depicted given explicit, specific, informed and freely given consent to "
    "that generation or alteration?",
    "Hat jede abgebildete Person in diese Erzeugung oder Veränderung ausdrücklich, für diesen "
    "Zweck, in Kenntnis der Umstände und freiwillig eingewilligt?",
)
GENERATION_PURPOSE = _question(
    "generation_purpose",
    "art:5:1a:a:i",
    "Is producing such material what the system is offered or built for?",
    "Ist das Erzeugen solchen Materials der Zweck, für den das System angeboten oder gebaut wird?",
)
FORESEEABLE_WITHOUT_SAFEGUARDS = _question(
    "foreseeable_without_safeguards",
    "art:5:1a:a:ii",
    "Can users readily get such material out of the system without modifying it, and does it "
    "lack safeguards that reliably prevent this and correct reported misuse?",
    "Können Nutzer solches Material ohne Änderungen am System ohne Weiteres erhalten, und "
    "fehlen Schutzmaßnahmen, die das zuverlässig verhindern und gemeldeten Missbrauch "
    "beheben?",
)
DEPLOYER_GENERATION_PURPOSE = _question(
    "deployer_generation_purpose",
    "art:5:1a:b",
    "Does your organisation itself use the system in order to produce such material?",
    "Nutzt Ihre Organisation das System selbst, um solches Material zu erzeugen?",
)

# --- Art. 5(1)(c) to (g) ------------------------------------------------------------------------

SOCIAL_SCORING = _question(
    "social_scoring",
    "art:5:1:c",
    "Does the system score or rank people over a period of time based on their social "
    "behaviour or their personal characteristics?",
    "Bewertet oder ordnet das System Menschen über einen Zeitraum hinweg nach ihrem sozialen "
    "Verhalten oder ihren persönlichen Merkmalen ein?",
)
UNRELATED_CONTEXT_TREATMENT = _question(
    "unrelated_context_treatment",
    "art:5:1:c:i",
    "Does the score lead to worse treatment of people in areas unrelated to where the data was "
    "collected?",
    "Führt die Bewertung dazu, dass Menschen in Bereichen schlechter behandelt werden, die mit "
    "dem Bereich, in dem die Daten erhoben wurden, nichts zu tun haben?",
)
DISPROPORTIONATE_TREATMENT = _question(
    "disproportionate_treatment",
    "art:5:1:c:ii",
    "Does the score lead to worse treatment that is unjustified or out of proportion to the "
    "behaviour it rests on?",
    "Führt die Bewertung zu einer schlechteren Behandlung, die ungerechtfertigt ist oder in "
    "keinem Verhältnis zu dem Verhalten steht, auf dem sie beruht?",
)
CRIME_RISK_ASSESSMENT = _question(
    "crime_risk_assessment",
    "art:5:1:d",
    "Does the system assess or predict how likely individual people are to commit a criminal "
    "offence?",
    "Bewertet oder prognostiziert das System, wie wahrscheinlich einzelne Menschen eine "
    "Straftat begehen?",
)
SOLELY_PROFILING = _question(
    "solely_profiling",
    "art:5:1:d",
    "Does that assessment rest only on profiling or on people's personality traits and "
    "characteristics?",
    "Beruht diese Bewertung allein auf Profiling oder auf Persönlichkeitsmerkmalen und "
    "Eigenschaften der Menschen?",
)
FACT_BASED_ASSESSMENT = _question(
    "fact_based_assessment",
    "art:5:1:d",
    "Does the system only support a person's assessment of someone's involvement in a crime "
    "that already rests on objective, verifiable facts linked to that crime?",
    "Unterstützt das System nur die Einschätzung eines Menschen zur Beteiligung einer Person an "
    "einer Straftat, die bereits auf objektiven, überprüfbaren Tatsachen zu dieser Straftat "
    "beruht?",
)
UNTARGETED_FACE_SCRAPING = _question(
    "untargeted_face_scraping",
    "art:5:1:e",
    "Does the system build or extend a facial recognition database by collecting facial images "
    "from the internet or CCTV footage without targeting specific people?",
    "Baut oder erweitert das System eine Gesichtserkennungsdatenbank, indem es Gesichtsbilder "
    "aus dem Internet oder aus Videoüberwachung sammelt, ohne gezielt bestimmte Personen zu "
    "suchen?",
)
INFERS_EMOTIONS = _question(
    "infers_emotions",
    "art:5:1:f",
    "Does the system infer people's emotions or intentions, such as stress, frustration or "
    "boredom, for example from their face, voice, typing or other signals of their body?",
    "Erkennt das System Gefühle oder Absichten von Menschen, etwa Stress, Frust oder "
    "Langeweile, zum Beispiel aus Gesicht, Stimme, Tippverhalten oder anderen Körpersignalen?",
)
WORKPLACE_OR_EDUCATION = _question(
    "workplace_or_education",
    "art:5:1:f",
    "Is the system used on people at their workplace or in an education institution?",
    "Wird das System bei Menschen an ihrem Arbeitsplatz oder in einer Bildungseinrichtung "
    "eingesetzt?",
)
MEDICAL_OR_SAFETY = _question(
    "medical_or_safety",
    "art:5:1:f",
    "Is the system put in place only for medical or safety reasons, with the results used for "
    "nothing else?",
    "Wird das System nur aus medizinischen Gründen oder aus Sicherheitsgründen eingesetzt, und "
    "werden die Ergebnisse für nichts anderes verwendet?",
)
BIOMETRIC_CATEGORISATION = _question(
    "biometric_categorisation",
    "art:5:1:g",
    "Does the system sort individual people into categories based on their biometric data, "
    "such as their face or voice?",
    "Ordnet das System einzelne Menschen anhand ihrer biometrischen Daten, etwa Gesicht oder "
    "Stimme, in Kategorien ein?",
)
SENSITIVE_TRAITS = _question(
    "sensitive_traits",
    "art:5:1:g",
    "Do those categories infer people's race, political opinions, trade union membership, "
    "religious or philosophical beliefs, sex life or sexual orientation?",
    "Schließen diese Kategorien auf die ethnische Herkunft, politische Meinungen, "
    "Gewerkschaftszugehörigkeit, religiöse oder weltanschauliche Überzeugungen, das "
    "Sexualleben oder die sexuelle Orientierung?",
)
LAWFUL_LABELLING = _question(
    "lawful_labelling",
    "art:5:1:g",
    "Does the system only label or filter lawfully acquired biometric datasets, or categorise "
    "biometric data for law enforcement?",
    "Kennzeichnet oder filtert das System nur rechtmäßig erworbene biometrische Datensätze, "
    "oder kategorisiert es biometrische Daten zur Strafverfolgung?",
)

# --- Art. 5(1)(h) and its conditions in Art. 5(2), (3) and (5) ----------------------------------

REAL_TIME_IDENTIFICATION = _question(
    "real_time_identification",
    "art:5:1:h",
    "Does the system identify people at a distance in real time, for example by matching faces "
    "from live cameras against a list, in places open to the public?",
    "Identifiziert das System Menschen aus der Ferne in Echtzeit, etwa indem es Gesichter aus "
    "Live-Kameras mit einer Liste abgleicht, an öffentlich zugänglichen Orten?",
)
LAW_ENFORCEMENT_USE = _question(
    "law_enforcement_use",
    "art:5:1:h",
    "Is it used by a law enforcement authority, or on its behalf, to prevent, investigate or "
    "prosecute crime?",
    "Wird es von einer Strafverfolgungsbehörde oder in ihrem Auftrag eingesetzt, um Straftaten "
    "zu verhüten, aufzuklären oder zu verfolgen?",
)
RBI_OBJECTIVE = _question(
    "rbi_objective",
    "art:5:1:h",
    "Is each use strictly necessary for one of these purposes: searching for specific victims "
    "of abduction, trafficking or sexual exploitation or for missing persons; preventing a "
    "specific, imminent threat to life or a terrorist attack; or locating a suspect of a "
    "serious offence listed in Annex II?",
    "Ist jeder Einsatz für einen dieser Zwecke unbedingt erforderlich: die Suche nach "
    "bestimmten Opfern von Entführung, Menschenhandel oder sexueller Ausbeutung oder nach "
    "vermissten Personen; die Abwehr einer konkreten, unmittelbaren Gefahr für Leib und Leben "
    "oder eines Terroranschlags; oder das Auffinden einer Person, die einer schweren Straftat "
    "nach Anhang II verdächtig ist?",
)
NATIONAL_LAW = _question(
    "national_law_authorisation",
    "art:5:5",
    "Does the law of your Member State allow this use for that purpose?",
    "Erlaubt das Recht Ihres Mitgliedstaats diesen Einsatz für diesen Zweck?",
)
PRIOR_AUTHORISATION = _question(
    "prior_authorisation",
    "art:5:3",
    "Is each use authorised in advance by a court or an independent administrative authority "
    "(or, in urgent cases, is the authorisation requested within 24 hours)?",
    "Wird jeder Einsatz vorab von einem Gericht oder einer unabhängigen Verwaltungsbehörde "
    "genehmigt (oder wird die Genehmigung in dringenden Fällen innerhalb von 24 Stunden "
    "beantragt)?",
)
TARGETED_USE = _question(
    "targeted_use",
    "art:5:2",
    "Is each use limited to confirming the identity of the specific person sought, and limited "
    "in time, place and the people concerned?",
    "Dient jeder Einsatz nur dazu, die Identität der gesuchten Person zu bestätigen, und ist er "
    "zeitlich, örtlich und auf die betroffenen Personen begrenzt?",
)
IMPACT_ASSESSMENT_REGISTRATION = _question(
    "impact_assessment_registration",
    "art:5:2",
    "Has a fundamental rights impact assessment (Art. 27) been completed and the system "
    "registered in the EU database (Art. 49)?",
    "Wurde eine Grundrechte-Folgenabschätzung (Art. 27) durchgeführt und das System in der "
    "EU-Datenbank registriert (Art. 49)?",
)

# --- A provider refusal (decision 029) -----------------------------------------------------------

PERSON_REVIEW = _question(
    "person_review",
    "art:5:1:ba",
    "Please have a person review the description: does the system generate or alter intimate or "
    "sexual images, video or audio of real people, or sexual material involving children "
    "(Art. 5(1)(ba), (bb))?",
    "Bitte lassen Sie die Beschreibung von einem Menschen prüfen: Erzeugt oder verändert das "
    "System intime oder sexuelle Bilder, Videos oder Tonaufnahmen realer Personen oder sexuelles "
    "Material, in dem Kinder vorkommen (Art. 5 Abs. 1 Buchst. ba, bb)?",
)
REFUSAL: Mapping[Language, str] = {
    EN: "The model provider's content filter blocked this description, so it could not be "
    "assessed automatically. Art. 5(1)(ba) or (bb) may apply: prohibited is assumed until a "
    "person has reviewed it.",
    DE: "Der Inhaltsfilter des Modellanbieters hat diese Beschreibung blockiert, daher konnte sie "
    "nicht automatisch geprüft werden. Art. 5 Abs. 1 Buchst. ba oder bb kann greifen: Bis ein "
    "Mensch sie geprüft hat, wird ein Verbot angenommen.",
}
REFUSAL_ERROR = "provider_refusal"
"""The step's error code for a refusal."""

# --- Naming and decision sentences --------------------------------------------------------------


def point_name(provision_id: str, language: Language) -> str:
    """How a result names an Art. 5 provision: `art:5:1:ba` is "Art. 5(1)(ba)" in English and
    "Art. 5 Abs. 1 Buchst. ba" in German; `art:5:1:c:i` is "Art. 5(1)(c)(i)" or "Art. 5 Abs. 1
    Buchst. c Ziff. i"."""
    _, article, paragraph, *points = provision_id.split(":")
    if language is DE:
        letters = ("Buchst.", "Ziff.")
        tail = "".join(f" {letters[min(n, 1)]} {p}" for n, p in enumerate(points))
        return f"Art. {article} Abs. {paragraph}{tail}"
    return f"Art. {article}({paragraph})" + "".join(f"({p})" for p in points)


TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "prohibited": "Prohibited under {points}.",
        "none": "No prohibited practice under Art. 5 matches.",
        "considered": "Considered {point}: {fact}",
        "missing": "Assumed prohibited under {point} until this is answered: {question}",
        "ambiguous": "Assumed prohibited under {point} pending legal review: {question}",
        "not_yet": "{point} applies only from {start} (Art. 113(a)), so on {as_of} it does "
        "not yet prohibit this system; from {start} it {verb} apply: {fact}",
        "not_yet_verb_met": "will",
        "not_yet_verb_open": "may",
        "notify": "Each use must be notified to the market surveillance authority and the "
        "national data protection authority (Art. 5(4)).",
    },
    DE: {
        "prohibited": "Verboten nach {points}.",
        "none": "Keine verbotene Praxis nach Art. 5 trifft zu.",
        "considered": "Geprüft: {point}: {fact}",
        "missing": "Bis zur Antwort auf diese Frage wird ein Verbot nach {point} angenommen: "
        "{question}",
        "ambiguous": "Bis zur rechtlichen Prüfung wird ein Verbot nach {point} angenommen: "
        "{question}",
        "not_yet": "{point} gilt erst ab dem {start} (Art. 113 Buchst. a), daher verbietet es "
        "dieses System am {as_of} noch nicht; ab dem {start} {verb}: {fact}",
        "not_yet_verb_met": "greift es",
        "not_yet_verb_open": "kann es greifen",
        "notify": "Jeder Einsatz muss der Marktüberwachungsbehörde und der nationalen "
        "Datenschutzbehörde gemeldet werden (Art. 5 Abs. 4).",
    },
}

OPEN_FALLBACK: Mapping[Language, tuple[str, str, str]] = {
    EN: (
        "Do the Act and guidance settle whether {point} applies to this system?",
        "Prohibited: {point} applies.",
        "Not prohibited: {point} does not apply.",
    ),
    DE: (
        "Klären Verordnung und Leitlinien, ob {point} auf dieses System zutrifft?",
        "Verboten: {point} trifft zu.",
        "Nicht verboten: {point} trifft nicht zu.",
    ),
}
"""The open question and its two readings (stricter first) when the model marks a practice
unsettled in law without stating the question: `(question, stricter, lenient)`."""
