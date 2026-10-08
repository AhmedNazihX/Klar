"""A drafted document laid out for Word and PDF (P9): its DRAFT stamp, title, law text and date,
the note, then each section's heading and content. A section still waiting shows the requirement
it answers (a skeleton's) and its "To fill in" marker, so nothing unfilled passes for content. A
vendor message's section shows the Art. 5(1) points it quotes, read from the corpus. The
disclaimer closes every page. Only the draft's own texts go in: the template's wording and
requirements, the corpus's quotes, the result's facts and the user's answers, exactly as the draft
holds them (never a text of the Act taken from the posted result, decision 031)."""

from collections.abc import Mapping

from aiact.dates import long_date
from aiact.drafting.models import DraftDocument, DraftSection, SectionStatus
from aiact.export import Block, FillMarker, Heading, Note, Paper, Paragraph, Quote
from aiact.provision_names import provision_name
from aiact.schemas import LAW_TEXTS, Citation, Language

EN, DE = Language.EN, Language.DE

STAMP: Mapping[Language, str] = {EN: "DRAFT", DE: "ENTWURF"}
PREPARED_WITH: Mapping[Language, str] = {
    EN: "Draft prepared with Klar.",
    DE: "Entwurf erstellt mit Klar.",
}
LAW_LINE: Mapping[Language, str] = {
    EN: "AI Act text: CELEX {celex}, as it applies on {date}.",
    DE: "Text der KI-Verordnung: CELEX {celex}, in der am {date} geltenden Fassung.",
}
SOURCE_LINE: Mapping[Language, str] = {
    EN: "{provision}, Regulation (EU) 2024/1689, consolidated text",
    DE: "{provision}, Verordnung (EU) 2024/1689, konsolidierte Fassung",
}
MARKERS: Mapping[SectionStatus, Mapping[Language, str]] = {
    SectionStatus.QUESTIONS: {EN: "To fill in.", DE: "Noch auszufüllen."},
    SectionStatus.TO_FILL_IN: {EN: "To fill in.", DE: "Noch auszufüllen."},
    SectionStatus.NEEDS_EVIDENCE: {
        EN: "To fill in: this section needs your evidence, such as test reports.",
        DE: "Noch auszufüllen: Dieser Abschnitt braucht Ihre Nachweise, etwa Prüfberichte.",
    },
    SectionStatus.GENERATED_LAST: {
        EN: "To fill in last, once every other section is complete.",
        DE: "Zuletzt auszufüllen, wenn alle anderen Abschnitte fertig sind.",
    },
}
"""The marker of a section still waiting, by what it waits for (the DocSkeleton statuses)."""


def document_paper(document: DraftDocument) -> Paper:
    """`document` as a `Paper` for `aiact.export`'s renderers."""
    language = document.language
    law_text = LAW_TEXTS[document.law_version]
    law_line = LAW_LINE[language].format(
        celex=law_text.celex, date=long_date(document.as_of, language.value)
    )
    note = (Note(document.note),) if document.note is not None else ()
    blocks = tuple(block for section in document.sections for block in _section(section, language))
    return Paper(
        language=language,
        title=document.title,
        stamp=STAMP[language],
        lines=(law_line,),
        blocks=(*note, *blocks),
        footer=f"{PREPARED_WITH[language]} {document.disclaimer}",
    )


def _section(section: DraftSection, language: Language) -> tuple[Block, ...]:
    """The heading, the paragraphs and the provisions the section quotes (a vendor message's
    Art. 5(1) points, read from the corpus), and, while the section waits, its requirement and
    marker."""
    content = (
        *(Paragraph(paragraph) for paragraph in section.paragraphs),
        *(_quote(citation) for citation in section.quotes),
    )
    if section.status is SectionStatus.DRAFTED:
        return (Heading(section.heading), *content)
    requirement = (_quote(section.requirement),) if section.requirement is not None else ()
    marker = FillMarker(MARKERS[section.status][language])
    return (Heading(section.heading), *content, *requirement, marker)


def _quote(citation: Citation) -> Quote:
    source = SOURCE_LINE[citation.language].format(
        provision=provision_name(citation.provision_id, citation.language)
    )
    return Quote(citation.quote, source)
