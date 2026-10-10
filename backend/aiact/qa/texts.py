"""The Q&A's fixed answers and its prompt (P7; decision 026, Ask).

A question not answered gets a fixed answer in its own language, never the model's words: one
for a question the corpus doesn't answer, one for a question about compliance, both naming what
Klar covers (the AI Act and the Commission's guidance on it) so the user knows where to look
instead; and one for a question both models refused (decision 033), which asking again won't
change.
"""

from collections.abc import Mapping
from types import MappingProxyType

from aiact.qa.models import AnswerKind
from aiact.schemas import Language

OUTSIDE_CORPUS_EN = (
    "That's outside what I can answer. I cover the AI Act and the Commission's guidance on it, "
    "and they don't answer this question."
)
OUTSIDE_CORPUS_DE = (
    "Das kann ich nicht beantworten. Ich behandle die KI-Verordnung und die Leitlinien der "
    "Kommission dazu, und diese Texte beantworten die Frage nicht."
)
COMPLIANCE_EN = (
    "That's outside what I can answer. I cover the AI Act and the Commission's guidance on it, "
    "and I don't say whether a company is compliant with any law.\n\n"
    "Your lawyer or compliance officer is the right person to ask."
)
COMPLIANCE_DE = (
    "Das kann ich nicht beantworten. Ich behandle die KI-Verordnung und die Leitlinien der "
    "Kommission dazu, und ich sage nicht, ob ein Unternehmen ein Gesetz einhält.\n\n"
    "Fragen Sie dazu Ihre Rechtsberatung oder Ihre Compliance-Abteilung."
)

REFUSED_EN = (
    "I can't answer this question: the language model declined to process it. Asking it again "
    "won't change that, but you can ask it in other words."
)
REFUSED_DE = (
    "Diese Frage kann ich nicht beantworten: Das Sprachmodell hat ihre Bearbeitung abgelehnt. "
    "Eine Wiederholung ändert daran nichts, aber Sie können die Frage anders formulieren."
)

NOT_ANSWERED: Mapping[AnswerKind, Mapping[Language, str]] = MappingProxyType(
    {
        AnswerKind.OUTSIDE_CORPUS: MappingProxyType(
            {Language.EN: OUTSIDE_CORPUS_EN, Language.DE: OUTSIDE_CORPUS_DE}
        ),
        AnswerKind.COMPLIANCE: MappingProxyType(
            {Language.EN: COMPLIANCE_EN, Language.DE: COMPLIANCE_DE}
        ),
        AnswerKind.REFUSED: MappingProxyType({Language.EN: REFUSED_EN, Language.DE: REFUSED_DE}),
    }
)
"""The fixed answer per kind not answered and language."""

LANGUAGE_NAMES: Mapping[Language, str] = MappingProxyType(
    {Language.EN: "English", Language.DE: "German"}
)

INSTRUCTIONS = """\
You answer questions about the EU AI Act and the European Commission's guidance on it, for \
people at small companies who are not lawyers. You answer only from the numbered sources the \
user gives you, never from memory.

Set `kind`:
- "compliance" when the question asks for a verdict on the asker's own compliance: whether \
their own company, tool or practice complies with, or is lawful under, the AI Act or any other \
law ("Are we compliant?", "Is our tool legal?", "Am I allowed to keep using our chatbot as it \
is?"). Klar never says whether anyone complies, so don't answer it. A question about what the \
AI Act allows, bans or requires in general is not a compliance question: answer it from the \
sources with their provisions ("May an employer use emotion recognition at work?", "Is social \
scoring banned?", "Do deployers have to tell people?").
- "outside_corpus" when the sources don't answer the question: it is about another EU or \
national law, or not about the AI Act at all, or the sources only touch its topic.
- "answered" otherwise.

When you answer:
- Lead with the direct answer in plain words, then the detail that matters. At most 150 words, \
in {language_name}. Plain text, no Markdown; separate paragraphs with a blank line.
- Never put source numbers in the text ("[1]", "(2, 3)", "Source 4"): they go in `cited` only. \
Name a provision as the Act does ("Article 26(1)", "Annex III") when it helps.
- In German, use the Act's official German terms: "KI-Verordnung" (never "AI Act"), \
"KI-System", "Anbieter", "Betreiber", "Hochrisiko-KI-System".
- Say only what the sources say. Don't add conditions, dates, exceptions or examples they don't \
contain, and don't quote more than a short phrase.
- Put the numbers of the sources your answer rests on in `cited`, most important first. Cite \
only sources that support what you say, and at least one.
- Never tell the user that they are or aren't compliant.

When `kind` isn't "answered", leave `answer` empty and `cited` empty."""

RESULT_INSTRUCTIONS = """

The user asks about a classification result Klar gave for their AI tool, shown below. Explain \
it from its steps and the sources; never re-decide the result or change its class."""

QUESTION = """\
{result}Sources:
{sources}

Question: {question}"""

RESULT_BLOCK = """\
The result asked about ({law_text}):
{lines}

"""
