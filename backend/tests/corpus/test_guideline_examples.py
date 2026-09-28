"""Decision 001's counting rules applied to hand-made blocks, and the anchor table itself."""

import re
from pathlib import Path

import pytest

from aiact.corpus.guideline_examples import (
    ANNEX_I_DOC,
    ANNEX_III_DOC,
    LIST_SIZES,
    Example,
    ExampleCountError,
    ExampleList,
    Segment,
    extract_examples,
    number_examples,
)
from aiact.corpus.guidelines_pdf import Block

DECISION_001 = (
    Path(__file__).resolve().parents[3] / "docs" / "decisions" / "001-commission-example-count.md"
)
ANCHOR_ROW_RE = re.compile(r"^\| \d+ \| (I|III) \|")


def heading(text: str, page: int = 1) -> Block:
    return Block("heading", text, page)


def bullet(text: str, page: int = 1) -> Block:
    return Block("list_item", text, page, "-")


def sub_bullet(text: str, page: int = 1) -> Block:
    return Block("list_item", text, page, "o")


def paragraph(text: str, page: int = 1, number: str = "") -> Block:
    return Block("list_item" if number else "paragraph", text, page, number)


def lists_of(segments: tuple[Segment, ...]) -> list[ExampleList]:
    return [s for s in segments if isinstance(s, ExampleList)]


ANNEX_III_BLOCKS = (
    heading("3.1.1. Biometric identification"),
    paragraph("Biometric identification needs a reference database.", number="(143)"),
    heading("a) Practical examples of AI systems falling within the high-risk use case"),
    bullet("Facial recognition for media archives."),
    heading("Prioritisation"),
    bullet("Voiceprint matching in databases."),
    paragraph("This system falls within the use case."),
    Block("footnote", "18 In line with ISO/IEC 2382-37.", 1),
    heading("b) Practical examples of AI systems falling outside the high-risk use case", 2),
    bullet("AI systems intended to be used for biometric verification:", 2),
    sub_bullet("AI based solutions to unlock a smartphone.", 2),
    sub_bullet("AI based solutions for online exam proctoring.", 2),
    bullet("Smart corridor biometrics.", 3),
    heading("3.1.2. Post remote biometric identification", 3),
    paragraph("Examples of targeted searches:", 3),
    bullet("Following an armed robbery, investigators compare CCTV images.", 3),
    heading("a) Practical example of an AI system falling outside of the supply of gas", 4),
    paragraph("AI system used as a predictive maintenance tool for gas pipelines.", 4),
    heading("a) Practical examples of an AI system falling within the supply of electricity", 5),
    paragraph("An AI system used in a surveillance and protection system.", 5),
    paragraph("An AI system used for the detection of anomalies.", 5),
    paragraph("For such systems, the following applies.", 5, number="(206)"),
    paragraph(
        "Examples of AI systems used solely for cybersecurity purposes, thus falling outside the "
        "use case of point 2 of Annex III AI Act:",
        6,
    ),
    bullet("An AI system that detects unauthorised access.", 6),
    Block("list_item", "The AI system must be used by a critical entity", 6, "ii."),
)


def test_annex_iii_lists_follow_the_counting_rules() -> None:
    segments = extract_examples(ANNEX_III_DOC, ANNEX_III_BLOCKS)
    lists = lists_of(segments)

    assert [[e.text for e in lst.examples] for lst in lists] == [
        [
            "Facial recognition for media archives.",
            # Paragraphs after a bullet are its body.
            "Voiceprint matching in databases.\nThis system falls within the use case.",
        ],
        [
            # One example per `o` sub-bullet; the bullet itself is their lead-in.
            "AI based solutions to unlock a smartphone.",
            "AI based solutions for online exam proctoring.",
            "Smart corridor biometrics.",
        ],
        # Headings without bullets: one example per paragraph.
        ["AI system used as a predictive maintenance tool for gas pipelines."],
        [
            "An AI system used in a surveillance and protection system.",
            "An AI system used for the detection of anomalies.",
        ],
        ["An AI system that detects unauthorised access."],
    ]
    assert lists[0].examples[1].subheading == "Prioritisation"
    assert (
        lists[1].examples[0].lead_in == "AI systems intended to be used for biometric verification:"
    )
    assert lists[1].examples[2].lead_in is None


def test_running_text_examples_and_list_endings_stay_prose() -> None:
    segments = extract_examples(ANNEX_III_DOC, ANNEX_III_BLOCKS)
    prose = [s.text for s in segments if isinstance(s, Block)]

    # "Examples of targeted searches" is a running-text illustration (decision 001, rule 5).
    assert "Following an armed robbery, investigators compare CCTV images." in prose
    # A numbered paragraph, a numbered heading or a section marker ends a list.
    assert "For such systems, the following applies." in prose
    assert "3.1.2. Post remote biometric identification" in prose
    assert "The AI system must be used by a critical entity" in prose
    # A footnote inside a list goes back to the prose.
    assert "18 In line with ISO/IEC 2382-37." in prose


def test_annex_i_named_paragraphs_give_the_examples() -> None:
    blocks = (
        paragraph(
            "By way of illustration, a combustion optimiser is a safety component. Conversely, "
            "a heating-schedule optimiser is not.",
            number="(43)",
        ),
        paragraph("Examples of safety components include:", number="(45)"),
        bullet("Machinery: a vision system that stops a robot."),
        bullet("Lifts: door closing timing."),
        paragraph("The AI Act does not classify products automatically.", number="(48)"),
        paragraph("By way of example, a smart thermostat is not one.", number="(49)"),
        paragraph("To be classified as high-risk, the product needs an assessment.", number="(50)"),
    )
    segments = extract_examples(ANNEX_I_DOC, blocks)

    assert [(lst.heading, [e.text for e in lst.examples]) for lst in lists_of(segments)] == [
        (
            "para. (43)",
            [
                "By way of illustration, a combustion optimiser is a safety component.",
                "Conversely, a heating-schedule optimiser is not.",
            ],
        ),
        (
            "para. (45)",
            ["Machinery: a vision system that stops a robot.", "Lifts: door closing timing."],
        ),
        ("para. (49)", ["By way of example, a smart thermostat is not one."]),
    ]
    prose = [s.text for s in segments if isinstance(s, Block)]
    assert prose == [
        "Examples of safety components include:",
        "The AI Act does not classify products automatically.",
        "To be classified as high-risk, the product needs an assessment.",
    ]


def test_other_documents_have_no_examples() -> None:
    blocks = (heading("a) Practical examples of prohibited practices"), bullet("A chatbot."))
    assert extract_examples("guide-prohibited", blocks) == blocks


def example_list(size: int) -> ExampleList:
    return ExampleList("h", 1, tuple(Example(f"example {i}", 1) for i in range(size)))


def test_numbering_runs_through_annex_i_then_annex_iii(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(LIST_SIZES, ANNEX_I_DOC, (2,))
    monkeypatch.setitem(LIST_SIZES, ANNEX_III_DOC, (1, 2))
    documents: dict[str, tuple[Segment, ...]] = {
        ANNEX_III_DOC: (example_list(1), heading("3.2."), example_list(2)),
        ANNEX_I_DOC: (example_list(2),),
    }
    numbered = number_examples(documents)

    ids = {
        doc: [e.example_id for lst in lists_of(numbered[doc]) for e in lst.examples]
        for doc in documents
    }
    assert ids == {
        ANNEX_I_DOC: ["hr-ex-001", "hr-ex-002"],
        ANNEX_III_DOC: ["hr-ex-003", "hr-ex-004", "hr-ex-005"],
    }


@pytest.mark.parametrize("annex_iii", [(example_list(1), example_list(1)), (example_list(1),)])
def test_a_list_that_differs_from_the_anchor_table_stops_the_numbering(
    monkeypatch: pytest.MonkeyPatch, annex_iii: tuple[Segment, ...]
) -> None:
    monkeypatch.setitem(LIST_SIZES, ANNEX_I_DOC, (1,))
    monkeypatch.setitem(LIST_SIZES, ANNEX_III_DOC, (1, 2))
    with pytest.raises(ExampleCountError, match="decision 001 counts"):
        number_examples({ANNEX_I_DOC: (example_list(1),), ANNEX_III_DOC: annex_iii})


def test_numbering_needs_both_parts() -> None:
    with pytest.raises(ExampleCountError, match="missing"):
        number_examples({ANNEX_I_DOC: ()})


def test_list_sizes_match_decision_001s_anchor_table() -> None:
    rows = [
        line.split("|")
        for line in DECISION_001.read_text(encoding="utf-8").splitlines()
        if ANCHOR_ROW_RE.match(line)
    ]
    anchors = {
        doc: tuple(int(row[7]) for row in rows if row[2].strip() == part)
        for doc, part in ((ANNEX_I_DOC, "I"), (ANNEX_III_DOC, "III"))
    }

    assert anchors == LIST_SIZES
    assert sum(map(sum, LIST_SIZES.values())) == 307
    assert sum(map(len, LIST_SIZES.values())) == 79
