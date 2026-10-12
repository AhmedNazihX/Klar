"""The fact a practice or route holds open in law, read on its stricter side (E19, option B).
The checks' own tests drive it through their answers; these pin the shared rules alone."""

import pytest

from aiact.engine.nodes.high_risk import STRICT_VALUES, AnnexIAnswer, AnnexIOpenOn
from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.open_in_law import NOT_NAMED, held_strict, open_field, stays_open
from aiact.schemas import EvidenceTag


def route(settled: Settled, on: AnnexIOpenOn, third_party: Answer = Answer.NO) -> AnnexIAnswer:
    return AnnexIAnswer(
        point="annex:I:A:11",
        covered=Answer.YES,
        safety_component_or_product=Answer.YES,
        third_party_assessment=third_party,
        settled_in_law=settled,
        open_question=None,
        open_on=on,
        evidence=EvidenceTag.INFERRED,
        fact="A made-up product route.",
        fact_numbers=(),
    )


def test_none_is_the_value_for_no_named_fact() -> None:
    assert NOT_NAMED == "none" == AnnexIOpenOn.NONE.value


@pytest.mark.parametrize(
    ("settled", "on", "expected"),
    [
        (Settled.NO, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, "third_party_assessment"),
        (Settled.NO, AnnexIOpenOn.NONE, None),
        (Settled.YES, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, None),
    ],
)
def test_only_an_unsettled_part_holds_a_named_fact_open(
    settled: Settled, on: AnnexIOpenOn, expected: str | None
) -> None:
    assert open_field(route(settled, on)) == expected


def test_the_open_fact_is_held_strict_in_a_new_copy() -> None:
    given = route(Settled.NO, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT)
    held = held_strict(given, STRICT_VALUES)
    assert held.third_party_assessment is Answer.YES
    assert given.third_party_assessment is Answer.NO  # the model's answer is left as it was
    assert held.covered is held.safety_component_or_product is Answer.YES


@pytest.mark.parametrize(
    ("settled", "on"),
    [(Settled.YES, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT), (Settled.NO, AnnexIOpenOn.NONE)],
)
def test_a_part_holding_no_named_fact_open_is_left_as_it_is(
    settled: Settled, on: AnnexIOpenOn
) -> None:
    given = route(settled, on)
    assert held_strict(given, STRICT_VALUES) is given


@pytest.mark.parametrize(
    ("settled", "on", "reading", "expected"),
    [
        pytest.param(Settled.YES, AnnexIOpenOn.NONE, Answer.YES, False, id="settled"),
        pytest.param(Settled.NO, AnnexIOpenOn.COVERED, Answer.YES, True, id="named-met"),
        pytest.param(Settled.NO, AnnexIOpenOn.COVERED, Answer.UNKNOWN, True, id="named-unknown"),
        pytest.param(Settled.NO, AnnexIOpenOn.COVERED, Answer.NO, False, id="named-ruled-out"),
        pytest.param(Settled.NO, AnnexIOpenOn.NONE, Answer.NO, True, id="unnamed-no"),
    ],
)
def test_only_another_fact_rules_an_open_part_out(
    settled: Settled, on: AnnexIOpenOn, reading: Answer, expected: bool
) -> None:
    assert stays_open(route(settled, on), reading) is expected
