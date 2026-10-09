"""Papers the renderer tests share: every kind of block, text that looks like markup, and enough
of it to run over a page."""

from aiact.export import (
    Fields,
    FillMarker,
    Heading,
    Note,
    PageBreak,
    Paper,
    Paragraph,
    Quote,
    SignOff,
    SmallText,
    Table,
)
from aiact.schemas import Language

MARKUP = "<b>Not bold</b> **not starred** {nb} &amp; <script>x</script>"
"""Text a markup reader would change: HTML, Markdown, fpdf2's page-count alias, an entity."""
FOOTER = "Draft prepared with Klar. Guidance, not legal advice."
LONG = "The provider tests the system on every release and keeps the results. " * 12


def sample_paper(language: Language = Language.EN, *, paragraphs: int = 1) -> Paper:
    return Paper(
        language=language,
        title="Größere Dokumentation: a test",
        stamp="DRAFT",
        lines=("AI Act text: CELEX 02024R1689-20260727, as it applies on 7 October 2026.",),
        blocks=(
            Note("A simplified form is expected."),
            Heading("The system"),
            Paragraph(MARKUP),
            Paragraph("Line one\nline two\x07"),
            Quote("the methods and steps performed for the development", "Annex IV 2"),
            FillMarker("To fill in."),
            *(Paragraph(LONG) for _ in range(paragraphs)),
        ),
        footer=FOOTER,
    )


def report_paper(language: Language = Language.EN) -> Paper:
    """A paper with the report's blocks: the kicker, the field grid, a table, a page break, a
    small text and the sign-off box."""
    return Paper(
        language=language,
        title="Applicant screening",
        kicker="Classification report · Report KR-0000ABCD",
        lines=("Prepared on 1 October 2026.",),
        blocks=(
            Fields((("Class", "High-risk"), ("Status", "Decided"))),
            Heading("Facts"),
            Table(("Fact", "Source"), ((MARKUP, "Stated by the user"),), (3.0, 1.0)),
            PageBreak(),
            Heading("Duties"),
            SmallText("Points for legal review."),
            SignOff("For the reviewer", ("Reviewed by", "Date"), "Not legal advice."),
        ),
        footer=FOOTER,
    )
