"""The fundamental rights impact assessment skeleton (Art. 27): one section per element the
assessment consists of, Art. 27(1) points (a) to (f). It is the deployer's duty (Art. 27(1)),
for the deployers that paragraph names; the result lists the duty with that condition.

The AI Office is to publish a questionnaire template (Art. 27(5)); until it does, the skeleton
follows paragraph 1.
"""

from aiact.drafting.models import DocumentKind
from aiact.drafting.skeletons.common import PREFILLED, ask, required
from aiact.drafting.templates import DE, EN, DocumentTemplate

ART_27_SKELETON = DocumentTemplate(
    id="art_27_fria",
    article="art:27:1",
    kind=DocumentKind.SKELETON,
    title={
        EN: "Fundamental rights impact assessment (Art. 27)",
        DE: "Grundrechte-Folgenabschätzung (Art. 27)",
    },
    sections=(
        *PREFILLED,
        required(
            "processes",
            ("Where the system is used", "Wo das System verwendet wird"),
            "art:27:1:a",
            ask(
                "processes",
                "In which of your processes will the system be used, in line with its intended "
                "purpose?",
                "In welchen Ihrer Verfahren wird das System im Einklang mit seiner "
                "Zweckbestimmung verwendet?",
            ),
        ),
        required(
            "period_and_frequency",
            ("Period and frequency of use", "Zeitraum und Häufigkeit der Verwendung"),
            "art:27:1:b",
            ask(
                "period_and_frequency",
                "Over what period, and how often, is the system intended to be used?",
                "In welchem Zeitraum und wie häufig soll das System verwendet werden?",
            ),
        ),
        required(
            "affected_people",
            ("People likely to be affected", "Voraussichtlich betroffene Personen"),
            "art:27:1:c",
            ask(
                "affected_people",
                "Which categories of people and groups are likely to be affected by its use "
                "in this context?",
                "Welche Kategorien natürlicher Personen und Personengruppen könnten von seiner "
                "Verwendung in diesem Kontext betroffen sein?",
            ),
        ),
        required(
            "risks_of_harm",
            ("Specific risks of harm", "Spezifische Schadensrisiken"),
            "art:27:1:d",
            ask(
                "risks_of_harm",
                "Which specific risks of harm are likely for those people and groups, taking "
                "into account the provider's information (Art. 13)?",
                "Welche spezifischen Schadensrisiken sind für diese Personen und Gruppen "
                "wahrscheinlich, unter Berücksichtigung der Informationen des Anbieters "
                "(Art. 13)?",
            ),
        ),
        required(
            "human_oversight",
            ("Human oversight", "Menschliche Aufsicht"),
            "art:27:1:e",
            ask(
                "human_oversight",
                "How do you implement human oversight, according to the instructions for use?",
                "Wie setzen Sie die menschliche Aufsicht entsprechend der Betriebsanleitung um?",
            ),
        ),
        required(
            "if_risks_materialise",
            ("If the risks materialise", "Wenn die Risiken eintreten"),
            "art:27:1:f",
            ask(
                "if_risks_materialise",
                "What will you do if those risks materialise, including your internal "
                "governance arrangements and complaint mechanisms?",
                "Was unternehmen Sie, wenn diese Risiken eintreten, einschließlich der "
                "Regelungen für die interne Unternehmensführung und der Beschwerdemechanismen?",
            ),
        ),
    ),
)
