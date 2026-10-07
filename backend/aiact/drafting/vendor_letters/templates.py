"""The two vendor letters, in English and German (decision 026 item 3; artboards ResultProhibited,
"Draft a message", and ResultAmbiguous, "Draft a request").

Each letter is its sections in order: who it goes to, the tool and who sends it are the user's
interview answers, word for word ("To fill in" until given); what the check found is pre-filled
from the result (`fills.py`); the request to the vendor is the template's fixed wording, which
claims nothing the result doesn't.
"""

from collections.abc import Mapping

from aiact.drafting.prefill import Fill
from aiact.drafting.templates import (
    DE,
    EN,
    ClassificationSection,
    DocumentTemplate,
    InterviewSection,
    TemplateSection,
)
from aiact.schemas import StepName

RECIPIENT = InterviewSection(
    "recipient",
    {EN: "To", DE: "An"},
    "vendor",
    {
        EN: "Which company supplies the tool? Give its name and the address to write to.",
        DE: "Welches Unternehmen liefert das Tool? Nennen Sie den Namen und die Anschrift, an die "
        "Sie schreiben.",
    },
)
TOOL = InterviewSection(
    "tool",
    {EN: "The tool", DE: "Das Tool"},
    "tool_name",
    {EN: "What is the tool called?", DE: "Wie heißt das Tool?"},
)
CHECKED = ClassificationSection("checked", {EN: "Our check", DE: "Unsere Prüfung"}, Fill.CHECKED)
SENDER = InterviewSection(
    "sender",
    {EN: "From", DE: "Absender"},
    "sender",
    {
        EN: "Who is sending the letter? Give your name, your role, and your company's name and "
        "address.",
        DE: "Wer sendet das Schreiben? Nennen Sie Ihren Namen, Ihre Funktion sowie Name und "
        "Anschrift Ihres Unternehmens.",
    },
)

# --- A prohibited result: the message ------------------------------------------------------------

PROHIBITED_MESSAGE = DocumentTemplate(
    id="vendor_message_prohibited",
    article="art:5",
    title={
        EN: "Message to the vendor: a prohibited practice",
        DE: "Nachricht an den Anbieter: eine verbotene Praktik",
    },
    sections=(
        RECIPIENT,
        TOOL,
        CHECKED,
        ClassificationSection(
            "finding", {EN: "What it found", DE: "Was sie ergeben hat"}, Fill.PROHIBITED_FINDING
        ),
        ClassificationSection(
            "facts",
            {EN: "The facts it rests on", DE: "Die Tatsachen, auf denen sie beruht"},
            Fill.DECIDING_FACTS,
            {
                EN: "The check names no facts it rests on.",
                DE: "Die Prüfung nennt keine Tatsachen, auf denen sie beruht.",
            },
        ),
        TemplateSection(
            "request",
            {EN: "What we ask of you", DE: "Worum wir Sie bitten"},
            {
                EN: "Please confirm in writing whether you agree with this finding, and tell us "
                "if any of the facts it rests on is wrong. If the finding holds, the AI Act "
                "prohibits placing the tool on the market, putting it into service and using it "
                "for this practice, so we ask you to stop supplying it to us for this use.",
                DE: "Bitte bestätigen Sie uns schriftlich, ob Sie diesem Ergebnis zustimmen, und "
                "teilen Sie uns mit, falls eine der Tatsachen, auf denen es beruht, nicht "
                "zutrifft. Trifft das Ergebnis zu, verbietet die KI-Verordnung, das Tool für "
                "diese Praktik in Verkehr zu bringen, in Betrieb zu nehmen und zu verwenden. Wir "
                "bitten Sie daher, es uns für diesen Zweck nicht weiter bereitzustellen.",
            },
        ),
        SENDER,
    ),
)

# --- A legally ambiguous result: the request -----------------------------------------------------

OPEN_QUESTION_ARTICLES: Mapping[StepName, str] = {
    StepName.SCOPE: "art:3",
    StepName.PROHIBITED: "art:5",
    StepName.HIGH_RISK: "art:6",
    StepName.TRANSPARENCY: "art:50",
    StepName.ROLE_OBLIGATIONS: "art:25",
}
"""The article each check's open question falls under, which the request is about: what makes
it an AI system (Art. 3), a prohibited practice (Art. 5), high-risk (Art. 6), a transparency
duty (Art. 50), or a deployer the provider (Art. 25, with the definitions of Art. 3). A question
whose applied reading rests on one of these articles is about that one instead: the role
check's own-name question is about Art. 3(3) (`DocumentTemplate.article_for`)."""

AMBIGUOUS_REQUEST = DocumentTemplate(
    id="vendor_request_ambiguous",
    article="art:6",
    open_question_articles=OPEN_QUESTION_ARTICLES,
    title={
        EN: "Request to the vendor: a point the law leaves open",
        DE: "Anfrage an den Anbieter: ein Punkt, den das Recht offenlässt",
    },
    sections=(
        RECIPIENT,
        TOOL,
        CHECKED,
        ClassificationSection(
            "question",
            {EN: "The point the law leaves open", DE: "Der Punkt, den das Recht offenlässt"},
            Fill.OPEN_QUESTION,
        ),
        ClassificationSection(
            "readings", {EN: "The two readings", DE: "Die beiden Lesarten"}, Fill.READINGS
        ),
        ClassificationSection(
            "settled_by",
            {EN: "What would settle it", DE: "Was den Punkt klären würde"},
            Fill.SETTLED_BY,
            {
                EN: "The check names nothing that would settle it.",
                DE: "Die Prüfung nennt nichts, was den Punkt klären würde.",
            },
        ),
        TemplateSection(
            "request",
            {EN: "What we ask of you", DE: "Worum wir Sie bitten"},
            {
                EN: "Please tell us how you read this point, and send us anything you hold that "
                "would settle it, such as an assessment you documented under the AI Act.",
                DE: "Bitte teilen Sie uns mit, wie Sie diesen Punkt beurteilen, und senden Sie "
                "uns Unterlagen, die ihn klären könnten, etwa eine Bewertung, die Sie nach der "
                "KI-Verordnung dokumentiert haben.",
            },
        ),
        SENDER,
    ),
)

VENDOR_LETTER_TEMPLATES: tuple[DocumentTemplate, ...] = (PROHIBITED_MESSAGE, AMBIGUOUS_REQUEST)
"""Both vendor letters, in the order the documents list shows them."""
