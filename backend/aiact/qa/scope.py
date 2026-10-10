"""Questions that ask whether someone complies (INIT > Ethical considerations: Q&A steers away
from "are we compliant?").

The plain forms are caught here, before any search or model call ("Are we compliant?", "Sind
wir konform?"); the model is told to recognise the rest (`texts.INSTRUCTIONS`). The patterns ask
whether *we*, *I* or *our tool* comply, as a yes/no question, so a question about what
compliance requires ("What do we need to do to comply with Article 50?", "Welche Pflichten
erfüllen wir als Betreiber?") still gets an answer.
"""

import re

SUBJECT_EN = r"(?:we|i|our|my|the company)"
SUBJECT_DE = r"(?:wir|ich|unser\w*|mein\w*)"
GAP = r"\b.{0,60}?\b"
"""A few words between the subject and the verdict word ("Are we, as a deployer, compliant")."""
START = r"(?:^|[.?!:]\s+)"
"""The yes/no question starts a sentence, so "What do we need to do to comply?" isn't one."""

COMPLIANCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"{START}(?:are|am|is|were)\s+{SUBJECT_EN}{GAP}(?:compliant|in compliance)\b",
        rf"{START}do(?:es)?\s+{SUBJECT_EN}{GAP}comply\b",
        rf"{START}(?:sind|bin|ist)\s+{SUBJECT_DE}{GAP}(?:konform|rechtskonform|regelkonform|compliant)\b",
    )
)


def is_compliance_question(question: str) -> bool:
    """Whether `question` asks, in English or German, whether the asker or their tool complies."""
    return any(pattern.search(question) for pattern in COMPLIANCE_PATTERNS)
