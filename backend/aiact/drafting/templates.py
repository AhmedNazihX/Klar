"""The section kinds every document template is built from, and the short deployer documents
(INIT > Documentation drafting), in English and German.

Each template lists its required sections in order. A section is pre-filled from the result
(`prefill.py`), filled with the user's interview answers word for word, or the template's own
fixed wording, which states only the duty the document answers. Nothing else enters a draft.
The provider document skeletons are in `skeletons/` (P8b).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from aiact.drafting.models import Provenance, SectionStatus
from aiact.drafting.prefill import Fill
from aiact.schemas import LAW_TEXTS, Citation, DocumentStatus, Language, LawVersion

EN, DE = Language.EN, Language.DE

Texts = Mapping[Language, str]


@dataclass(frozen=True)
class Question:
    """One interview question, stored under `key` in `interview_answers.question_key`."""

    key: str
    text: Texts


@dataclass(frozen=True)
class TemplateSection:
    """Fixed wording, the same in every draft of the template."""

    key: str
    heading: Texts
    text: Texts
    provenance: Provenance = Provenance.TEMPLATE


@dataclass(frozen=True)
class InterviewSection:
    """Filled with the answer to `question`, exactly as given; "To fill in" until answered."""

    key: str
    heading: Texts
    question_key: str
    question: Texts
    provenance: Provenance = Provenance.INTERVIEW


@dataclass(frozen=True)
class ClassificationSection:
    """Pre-filled from the classification result with what `fill` names. When the result has
    nothing for it, the section holds the fixed `empty` line instead (a template section)."""

    key: str
    heading: Texts
    fill: Fill
    empty: Texts | None = None
    provenance: Provenance = Provenance.CLASSIFICATION

    def __post_init__(self) -> None:
        if self.fill is Fill.SYSTEM_FACTS and self.empty is None:
            raise ValueError(f"section {self.key!r} needs its line for when no facts were stated")


AMENDED_TEXT = LAW_TEXTS[LawVersion.AMENDED]
"""The text a skeleton quotes: the duties are modelled for the amended Act only (decision 020),
so a skeleton quotes the requirements in force, whichever version the result was checked
against."""


@dataclass(frozen=True)
class Requirement:
    """A provision's requirement, quoted word for word from the amended AI Act: the English text
    and the official German one, as `get_provision` returns them (a test keeps them equal)."""

    provision_id: str
    quote: Texts

    def citation(self, language: Language) -> Citation:
        return Citation(
            provision_id=self.provision_id,
            document_id=AMENDED_TEXT.document_id,
            law_version=LawVersion.AMENDED,
            document_status=DocumentStatus.CONSOLIDATED,
            language=language,
            quote=self.quote[language],
        )


@dataclass(frozen=True)
class RequirementSection:
    """A section a provision requires (a skeleton's): the requirement quoted, and the interview
    questions whose answers fill it, each answer word for word as a paragraph in the order
    asked. `waits_for` is what the section shows until every question is answered."""

    key: str
    heading: Texts
    requirement: Requirement
    questions: tuple[Question, ...]
    waits_for: SectionStatus = SectionStatus.QUESTIONS
    provenance: Provenance = Provenance.INTERVIEW

    def __post_init__(self) -> None:
        if not self.questions:
            raise ValueError(f"section {self.key!r} needs a question that fills it")
        if self.waits_for is SectionStatus.DRAFTED:
            raise ValueError(f"section {self.key!r} can't wait for nothing")


SectionSpec = TemplateSection | InterviewSection | ClassificationSection | RequirementSection


def section_questions(spec: SectionSpec) -> tuple[Question, ...]:
    """The questions whose answers fill `spec`, in order; none for a pre-filled or fixed one."""
    if isinstance(spec, InterviewSection):
        return (Question(spec.question_key, spec.question),)
    if isinstance(spec, RequirementSection):
        return spec.questions
    return ()


@dataclass(frozen=True)
class DocumentTemplate:
    """A document answering one duty (`article`), with its required sections in order.

    `small_company_note` is the line a draft carries for an SME or a small mid-cap (the Annex IV
    skeleton's "simplified form expected", P8b)."""

    id: str
    article: str
    title: Texts
    sections: tuple[SectionSpec, ...]
    small_company_note: Texts | None = None

    @property
    def questions(self) -> tuple[Question, ...]:
        """The interview questions, in the order the sections ask them."""
        return tuple(question for spec in self.sections for question in section_questions(spec))


# --- Shared sections ------------------------------------------------------------------------------


NO_STATED_FACTS: Texts = {
    EN: "The description of the system stated no facts about it.",
    DE: "Die Beschreibung des Systems nennt keine Tatsachen über das System.",
}
"""The system section's line when the user stated no facts (Klar doesn't fill in its own)."""


def _system(heading: Texts) -> ClassificationSection:
    return ClassificationSection("system", heading, Fill.SYSTEM_FACTS, NO_STATED_FACTS)


DUTY = ClassificationSection(
    "duty", {EN: "Its classification", DE: "Seine Einstufung"}, Fill.CLASSIFICATION_AND_DUTY
)
TOOL = InterviewSection(
    "tool",
    {EN: "The tool and its supplier", DE: "Das Tool und sein Anbieter"},
    "tool_and_supplier",
    {
        EN: "What is the tool called, and who supplies it?",
        DE: "Wie heißt das Tool, und wer liefert es?",
    },
)
WHY_TELLING = {EN: "Why we're telling you", DE: "Warum wir Sie informieren"}
NOTICE = {EN: "The notice", DE: "Der Hinweis"}
WHY_SHOWN = {EN: "Why it is shown", DE: "Warum er angezeigt wird"}
PLACEMENT = InterviewSection(
    "placement",
    {EN: "Where it is shown", DE: "Wo er angezeigt wird"},
    "placement",
    {
        EN: "Where and when will people see this notice?",
        DE: "Wo und wann sehen Personen diesen Hinweis?",
    },
)

# --- Art. 26(2): human oversight record ----------------------------------------------------------

OVERSIGHT_RECORD = DocumentTemplate(
    id="art_26_2_oversight",
    article="art:26:2",
    title={EN: "Human oversight record", DE: "Nachweis der menschlichen Aufsicht"},
    sections=(
        _system({EN: "The system", DE: "Das System"}),
        DUTY,
        TemplateSection(
            "why",
            {EN: "Why we keep this record", DE: "Warum wir diesen Nachweis führen"},
            {
                EN: "Under Article 26(2) of the EU AI Act, a deployer of a high-risk AI system "
                "must assign human oversight to people who have the necessary competence, "
                "training and authority, and give them the support they need.",
                DE: "Nach Artikel 26 Absatz 2 der KI-Verordnung muss ein Betreiber eines "
                "Hochrisiko-KI-Systems die menschliche Aufsicht natürlichen Personen übertragen, "
                "die über die erforderliche Kompetenz, Ausbildung und Befugnis verfügen, und "
                "ihnen die nötige Unterstützung geben.",
            },
        ),
        InterviewSection(
            "overseers",
            {EN: "Who oversees the system", DE: "Wer das System beaufsichtigt"},
            "overseers",
            {
                EN: "Who is assigned to oversee the system? Give names or roles.",
                DE: "Wem ist die Aufsicht über das System übertragen? Nennen Sie Namen oder "
                "Funktionen.",
            },
        ),
        InterviewSection(
            "competence",
            {EN: "Their competence and training", DE: "Kompetenz und Ausbildung"},
            "competence",
            {
                EN: "What competence and training do they have for this task?",
                DE: "Welche Kompetenz und Ausbildung haben sie für diese Aufgabe?",
            },
        ),
        InterviewSection(
            "authority",
            {EN: "Their authority and support", DE: "Befugnisse und Unterstützung"},
            "authority",
            {
                EN: "What authority and support do they have, for example to stop the system or "
                "override its output?",
                DE: "Welche Befugnisse und welche Unterstützung haben sie, zum Beispiel um das "
                "System anzuhalten oder seine Ergebnisse zu übergehen?",
            },
        ),
    ),
)

# --- Art. 26(7): notice to workers' representatives ----------------------------------------------

WORKERS_NOTICE = DocumentTemplate(
    id="art_26_7_workers",
    article="art:26:7",
    title={EN: "Notice to workers' representatives", DE: "Information der Arbeitnehmervertreter"},
    sections=(
        _system({EN: "What we plan to use", DE: "Was wir einsetzen wollen"}),
        DUTY,
        TemplateSection(
            "why",
            WHY_TELLING,
            {
                EN: "Under Article 26(7) of the EU AI Act, an employer must inform workers' "
                "representatives and the workers affected before it puts a high-risk AI system "
                "into service or uses it at the workplace.",
                DE: "Nach Artikel 26 Absatz 7 der KI-Verordnung muss ein Arbeitgeber die "
                "Arbeitnehmervertreter und die betroffenen Arbeitnehmer informieren, bevor er ein "
                "Hochrisiko-KI-System am Arbeitsplatz in Betrieb nimmt oder verwendet.",
            },
        ),
        InterviewSection(
            "recipients",
            {EN: "Who this notice is for", DE: "An wen sich diese Information richtet"},
            "recipients",
            {
                EN: "Is there a works council? Who receives this notice?",
                DE: "Gibt es einen Betriebsrat? Wer erhält diese Information?",
            },
        ),
        TOOL,
        InterviewSection(
            "start",
            {EN: "When we start", DE: "Wann wir beginnen"},
            "start_date",
            {EN: "When do you plan to start?", DE: "Wann wollen Sie beginnen?"},
        ),
        InterviewSection(
            "reviewer",
            {EN: "Who reviews the tool's output", DE: "Wer die Ergebnisse des Tools prüft"},
            "reviewer",
            {EN: "Who reviews the tool's output?", DE: "Wer prüft die Ergebnisse des Tools?"},
        ),
    ),
)

# --- Art. 26(11): notice to the people affected --------------------------------------------------

AFFECTED_NOTICE = DocumentTemplate(
    id="art_26_11_affected",
    article="art:26:11",
    title={EN: "Notice to the people affected", DE: "Information der betroffenen Personen"},
    sections=(
        _system({EN: "What we use", DE: "Was wir einsetzen"}),
        DUTY,
        TemplateSection(
            "why",
            WHY_TELLING,
            {
                EN: "Under Article 26(11) of the EU AI Act, a deployer of a high-risk AI system "
                "listed in Annex III that makes decisions, or helps make decisions, about people "
                "must inform those people that the system is used.",
                DE: "Nach Artikel 26 Absatz 11 der KI-Verordnung muss ein Betreiber eines in "
                "Anhang III genannten Hochrisiko-KI-Systems, das Entscheidungen über natürliche "
                "Personen trifft oder dabei unterstützt, diese Personen darüber informieren, dass "
                "das System bei ihnen verwendet wird.",
            },
        ),
        TOOL,
        InterviewSection(
            "decisions",
            {EN: "What it is used for", DE: "Wofür es verwendet wird"},
            "decisions",
            {
                EN: "Which decisions about people does the tool make or help make?",
                DE: "Welche Entscheidungen über Personen trifft das Tool oder bereitet es vor?",
            },
        ),
        InterviewSection(
            "contact",
            {EN: "Who to contact", DE: "An wen Sie sich wenden können"},
            "contact",
            {
                EN: "Who can people contact with questions about the tool?",
                DE: "An wen können sich Personen mit Fragen zum Tool wenden?",
            },
        ),
    ),
)

# --- Art. 50: disclosure texts -------------------------------------------------------------------

EMOTION_BIOMETRIC_DISCLOSURE = DocumentTemplate(
    id="art_50_3_disclosure",
    article="art:50:3",
    title={
        EN: "Disclosure: emotion recognition or biometric categorisation",
        DE: "Hinweis: Emotionserkennung oder biometrische Kategorisierung",
    },
    sections=(
        DUTY,
        TemplateSection(
            "notice",
            NOTICE,
            {
                EN: "An AI system for emotion recognition or biometric categorisation is in "
                "operation here.",
                DE: "Hier ist ein KI-System zur Emotionserkennung oder biometrischen "
                "Kategorisierung in Betrieb.",
            },
        ),
        TemplateSection(
            "why",
            WHY_SHOWN,
            {
                EN: "Under Article 50(3) of the EU AI Act, a deployer of an emotion recognition "
                "or biometric categorisation system must inform the people exposed to it that it "
                "is operating, and process their personal data in line with the GDPR.",
                DE: "Nach Artikel 50 Absatz 3 der KI-Verordnung muss ein Betreiber eines "
                "Emotionserkennungssystems oder eines Systems zur biometrischen Kategorisierung "
                "die betroffenen Personen über den Betrieb des Systems informieren und ihre "
                "personenbezogenen Daten im Einklang mit der DSGVO verarbeiten.",
            },
        ),
        PLACEMENT,
        InterviewSection(
            "contact",
            {EN: "Who to contact about your data", DE: "Ansprechpartner für Ihre Daten"},
            "contact",
            {
                EN: "Who can people contact about how their personal data is processed?",
                DE: "An wen können sich Personen zur Verarbeitung ihrer personenbezogenen Daten "
                "wenden?",
            },
        ),
    ),
)

GENERATED_CONTENT_DISCLOSURE = DocumentTemplate(
    id="art_50_4_disclosure",
    article="art:50:4",
    title={
        EN: "Disclosure: AI-generated or manipulated content",
        DE: "Hinweis: KI-erzeugte oder manipulierte Inhalte",
    },
    sections=(
        DUTY,
        TemplateSection(
            "notice",
            NOTICE,
            {
                EN: "This content has been artificially generated or manipulated.",
                DE: "Dieser Inhalt wurde künstlich erzeugt oder manipuliert.",
            },
        ),
        TemplateSection(
            "why",
            WHY_SHOWN,
            {
                EN: "Under Article 50(4) of the EU AI Act, a deployer must disclose that "
                "deep-fake image, audio or video content, or text published to inform the public "
                "on matters of public interest, has been artificially generated or manipulated.",
                DE: "Nach Artikel 50 Absatz 4 der KI-Verordnung muss ein Betreiber offenlegen, "
                "dass Deepfake-Bild-, Ton- oder Videoinhalte oder Texte, die veröffentlicht "
                "werden, um die Öffentlichkeit über Angelegenheiten von öffentlichem Interesse zu "
                "informieren, künstlich erzeugt oder manipuliert wurden.",
            },
        ),
        PLACEMENT,
    ),
)

DEPLOYER_TEMPLATES: tuple[DocumentTemplate, ...] = (
    OVERSIGHT_RECORD,
    WORKERS_NOTICE,
    AFFECTED_NOTICE,
    EMOTION_BIOMETRIC_DISCLOSURE,
    GENERATED_CONTENT_DISCLOSURE,
)
"""Every short deployer document, in the order the documents list shows them. Of the Art. 50
duties only (3) and (4) are a deployer's; (1) and (2) are the provider's (P28)."""
