"""The fact a practice or route holds open in law, read on its stricter side (E19, option B).
The checks' own tests drive it through their answers; these pin the shared rules alone."""

import pytest

from aiact.engine.nodes.high_risk import ANNEX_I_FACTS
from aiact.engine.nodes.high_risk_answer import STRICT_VALUES, AnnexIAnswer, AnnexIOpenOn
from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.open_in_law import (
    NOT_NAMED,
    held_strict,
    open_field,
    raised,
    stays_open,
)
from aiact.schemas import EvidenceTag

COVERED_ONLY = frozenset({"covered"})
"""A made-up point that reads only `covered` of the part, as a misnamed fact's test needs."""


def route(
    settled: Settled,
    on: AnnexIOpenOn,
    third_party: Answer = Answer.NO,
    covered: Answer = Answer.YES,
) -> AnnexIAnswer:
    return AnnexIAnswer(
        point="annex:I:A:11",
        covered=covered,
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
    ("settled", "on", "facts", "expected"),
    [
        pytest.param(
            Settled.NO,
            AnnexIOpenOn.THIRD_PARTY_ASSESSMENT,
            ANNEX_I_FACTS,
            "third_party_assessment",
            id="named",
        ),
        pytest.param(Settled.NO, AnnexIOpenOn.NONE, ANNEX_I_FACTS, None, id="unnamed"),
        pytest.param(
            Settled.YES, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, ANNEX_I_FACTS, None, id="settled"
        ),
        pytest.param(
            Settled.NO, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, COVERED_ONLY, None, id="misnamed"
        ),
    ],
)
def test_only_an_unsettled_part_holds_a_fact_its_points_read_open(
    settled: Settled, on: AnnexIOpenOn, facts: frozenset[str], expected: str | None
) -> None:
    """R2: a name no point of the part reads counts as no name."""
    assert open_field(route(settled, on), facts) == expected


def test_the_open_fact_is_held_strict_in_a_new_copy() -> None:
    given = route(Settled.NO, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT)
    held = held_strict(given, STRICT_VALUES, ANNEX_I_FACTS)
    assert held.third_party_assessment is Answer.YES
    assert given.third_party_assessment is Answer.NO  # the model's answer is left as it was
    assert held.covered is held.safety_component_or_product is Answer.YES


@pytest.mark.parametrize(
    ("settled", "on", "facts"),
    [
        pytest.param(Settled.YES, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, ANNEX_I_FACTS, id="settled"),
        pytest.param(Settled.NO, AnnexIOpenOn.NONE, ANNEX_I_FACTS, id="unnamed"),
        pytest.param(Settled.NO, AnnexIOpenOn.THIRD_PARTY_ASSESSMENT, COVERED_ONLY, id="misnamed"),
    ],
)
def test_a_part_holding_no_fact_its_points_read_open_is_left_as_it_is(
    settled: Settled, on: AnnexIOpenOn, facts: frozenset[str]
) -> None:
    given = route(settled, on)
    assert held_strict(given, STRICT_VALUES, facts) is given


@pytest.mark.parametrize(
    ("settled", "on", "covered", "expected"),
    [
        pytest.param(Settled.YES, AnnexIOpenOn.NONE, Answer.YES, True, id="gate-yes"),
        pytest.param(Settled.YES, AnnexIOpenOn.NONE, Answer.UNKNOWN, True, id="gate-unknown"),
        pytest.param(Settled.YES, AnnexIOpenOn.NONE, Answer.NO, False, id="gate-no-settled"),
        pytest.param(Settled.NO, AnnexIOpenOn.NONE, Answer.NO, False, id="gate-no-unnamed"),
        pytest.param(
            Settled.NO,
            AnnexIOpenOn.SAFETY_COMPONENT_OR_PRODUCT,
            Answer.NO,
            False,
            id="gate-no-other-named",
        ),
        pytest.param(Settled.NO, AnnexIOpenOn.COVERED, Answer.NO, True, id="gate-named"),
    ],
)
def test_a_gate_answered_no_rules_the_point_out_unless_it_is_the_open_fact(
    settled: Settled, on: AnnexIOpenOn, covered: Answer, expected: bool
) -> None:
    """R1: whatever `settled_in_law` and `open_on` say, only an open gate raises a point whose
    gate reads "no"."""
    part = route(settled, on, covered=covered)
    assert raised(part, "covered", part.covered, ANNEX_I_FACTS) is expected


@pytest.mark.parametrize(
    ("settled", "on", "reading", "own", "expected"),
    [
        pytest.param(
            Settled.YES, AnnexIOpenOn.NONE, Answer.YES, ANNEX_I_FACTS, False, id="settled"
        ),
        pytest.param(
            Settled.NO, AnnexIOpenOn.COVERED, Answer.YES, ANNEX_I_FACTS, True, id="named-met"
        ),
        pytest.param(
            Settled.NO,
            AnnexIOpenOn.COVERED,
            Answer.UNKNOWN,
            ANNEX_I_FACTS,
            True,
            id="named-unknown",
        ),
        pytest.param(
            Settled.NO, AnnexIOpenOn.COVERED, Answer.NO, ANNEX_I_FACTS, False, id="named-ruled-out"
        ),
        pytest.param(
            Settled.NO, AnnexIOpenOn.NONE, Answer.NO, ANNEX_I_FACTS, True, id="unnamed-no"
        ),
        pytest.param(
            Settled.NO,
            AnnexIOpenOn.THIRD_PARTY_ASSESSMENT,
            Answer.YES,
            COVERED_ONLY,
            False,
            id="named-for-another-point",
        ),
    ],
)
def test_only_another_fact_rules_an_open_point_out(
    settled: Settled, on: AnnexIOpenOn, reading: Answer, own: frozenset[str], expected: bool
) -> None:
    """R3 in the last case: a question open on a fact only another point of the part reads
    holds nothing open for this one."""
    assert stays_open(route(settled, on), reading, own, ANNEX_I_FACTS) is expected
