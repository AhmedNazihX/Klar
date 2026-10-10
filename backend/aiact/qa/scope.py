"""Questions that ask whether someone complies (INIT > Ethical considerations: Q&A steers away
from "are we compliant?").

The plain forms are caught here, before any search or model call ("Are we compliant?", "Sind
wir konform?"); the model is told to recognise the rest (`texts.INSTRUCTIONS`). The patterns ask
whether *we*, *I* or *our tool* comply, as a yes/no question about the verdict, so a question
about what compliance requires still gets an answer: one that starts elsewhere ("What do we
need to do to comply with Article 50?"), and one with a duty word between the subject and the
verdict ("Do we need to comply with Article 50?", "Are we obliged to label deepfakes in
compliance with Article 50?", "Sind wir als Betreiber verpflichtet, konform zu sein?").
"""

import re

SUBJECT_EN = r"(?:we|i|our|my|the company)"
SUBJECT_DE = r"(?:wir|ich|unser\w*|mein\w*)"
DUTY_WORDS = (
    r"need|needs|have\s+to|has\s+to|must|obliged|obligated|required|bound|supposed|should"
    r"|müssen|muss|verpflichtet|gezwungen|gehalten|brauchen|sollen|soll"
)
"""Words that ask what is required, not whether it is met: none may stand in the gap."""
GAP = rf"\b(?:(?!\b(?:{DUTY_WORDS})\b).){{0,60}}?\b"
"""A few words between the subject and the verdict word ("Are we, as a deployer, compliant"),
none of them a duty word."""
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
