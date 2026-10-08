"""Papers the renderer tests share: every kind of block, text that looks like markup, and enough
of it to run over a page."""

from aiact.export import FillMarker, Heading, Note, Paper, Paragraph, Quote
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
