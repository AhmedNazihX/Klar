"""The citation existence validator (aiact/engine/citations.py, E9) against the corpus built from
the committed `data/parsed/` (`tests/engine/built_corpus.py`), so no database is needed."""

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.corpus.build import OMNIBUS_DOC, DocumentLoad, DocumentRow, ProvisionRow
from aiact.engine.citations import (
    CITATION_UNVERIFIED,
    UNVERIFIED,
    CitationCheck,
    CitationValidator,
    check_citations,
    load_omnibus_changes,
    resolve,
)
from aiact.engine.graph import build_graph
from aiact.engine.nodes.common import Lookup
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineInput, EngineState
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.schemas import (
    PROVIDER_REFUSAL,
    Citation,
    ClassificationResult,
    DocumentStatus,
    FollowUpQuestion,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import get_settings
from tests.engine.built_corpus import (
    BuiltCorpus,
    built_corpus,
    built_validator,
    omnibus_changes,
)

AS_OF = date(2026, 12, 10)
"""After the Omnibus (27 July 2026) and its December prohibitions."""
BEFORE_OMNIBUS = date(2026, 3, 1)
AMENDED = "ai-act-consolidated"
ORIGINAL = "ai-act"

ENGINE_INPUT: EngineInput = {
    "description": "A tool that ranks job applicants.",
    "language": Language.EN,
    "law_version": LawVersion.AMENDED,
    "as_of": AS_OF,
    "exclude_source_example_ids": (),
}
STATE: EngineState = {**ENGINE_INPUT}


def lookup(
    as_of: date | None = AS_OF,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
) -> Lookup:
    return Lookup(
        language=language, law_version=law_version, as_of=as_of, exclude_source_example_ids=()
    )


def cite(
    provision_id: str,
    document_id: str = AMENDED,
    law_version: LawVersion | None = LawVersion.AMENDED,
    language: Language = Language.EN,
    quote: str = "As the node quoted it.",
) -> Citation:
    return Citation(
        provision_id=provision_id,
        document_id=document_id,
        law_version=law_version,
        language=language,
        quote=quote,
    )


ART_5_1_BA = cite("art:5:1:ba")
ART_4_ORIGINAL = cite("art:4", ORIGINAL, LawVersion.ORIGINAL)
FAKE = cite("art:5:1:zz")
"""Art. 5(1) has no point (zz): the injected fake citation."""


def checked(*citations: Citation, at: Lookup | None = None) -> CitationCheck:
    return check_citations(citations, at or lookup(), built_corpus(), omnibus_changes())


def marks(citation: Citation, at: Lookup | None = None) -> bool:
    result = checked(citation, at=at)
    assert not result.unresolved, result.unresolved
    (verified,) = result.verified
    return verified.changed_by_omnibus


# --- The Omnibus marker ---------------------------------------------------------------------------


def test_the_amendment_records_are_c1s() -> None:
    changes = load_omnibus_changes(get_settings().aiact_data_dir)
    assert changes.in_force_from == date(2026, 7, 27)
    assert {"art:5:1:ba", "art:5:1:bb", "art:4"} <= changes.targets


def test_art_5_1_ba_carries_the_marker_and_art_4_original_does_not() -> None:
    assert marks(ART_5_1_BA)
    assert not marks(ART_4_ORIGINAL, at=lookup(None, law_version=LawVersion.ORIGINAL))


@pytest.mark.parametrize(
    ("provision_id", "is_marked"),
    [
        ("art:4", True),  # replaced
        ("art:5", True),  # contains the inserted points (ba) and (bb)
        ("art:5:1:a", False),  # a sibling of the new points, unchanged
        ("art:50:1", False),  # Art. 50(7) changed, not 50(1)
        ("art:6:3", False),
    ],
)
def test_the_marker_follows_the_amendment_targets(provision_id: str, is_marked: bool) -> None:
    assert marks(cite(provision_id)) is is_marked


def test_the_amended_text_before_the_omnibus_carries_no_marker() -> None:
    assert not marks(cite("art:4"), at=lookup(BEFORE_OMNIBUS))


def test_a_german_citation_carries_the_marker_too() -> None:
    german = cite("art:5:1:ba", language=Language.DE)
    assert marks(german, at=lookup(language=Language.DE))


# --- Existence ------------------------------------------------------------------------------------


def test_a_resolved_citation_quotes_the_corpus() -> None:
    (verified,) = checked(ART_5_1_BA).verified
    assert verified.quote != ART_5_1_BA.quote
    assert verified.quote.startswith("the placing on the market")
    assert verified.document_status is DocumentStatus.CONSOLIDATED
    assert (verified.provision_id, verified.document_id) == ("art:5:1:ba", AMENDED)


@pytest.mark.parametrize(
    ("citation", "at"),
    [
        pytest.param(FAKE, lookup(), id="unknown-provision"),
        pytest.param(cite("art:5:1:ba", "ai-act-2024"), lookup(), id="not-the-manifest-key"),
        pytest.param(cite("art:5:1:ba", ORIGINAL), lookup(), id="document-of-another-version"),
        pytest.param(
            cite("art:5:1:ba", ORIGINAL, LawVersion.ORIGINAL),
            lookup(None, law_version=LawVersion.ORIGINAL),
            id="not-in-the-original-text",
        ),
        pytest.param(cite("art:5:1:ba"), lookup(date(2026, 3, 1)), id="not-yet-inserted"),
        pytest.param(cite("art:4", law_version=None), lookup(), id="law-without-its-version"),
        pytest.param(cite("Art. 4"), lookup(), id="malformed-id"),
        pytest.param(cite("point:4"), lookup(), id="no-known-kind-of-id"),
        pytest.param(cite("Art. 1", "omnibus", None), lookup(), id="malformed-omnibus-id"),
        pytest.param(
            cite("guide:guide-high-risk-annex-iii:ex:013", "guide-high-risk-annex-iii", None),
            lookup(),
            id="held-out-example",
        ),
        pytest.param(
            cite("guide:guide-art50:para:1", "guide-art50", None, Language.DE),
            lookup(language=Language.DE),
            id="german-quote-of-english-only-guidance",
        ),
        pytest.param(cite("art:1:1", "omnibus"), lookup(), id="omnibus-with-a-law-version"),
    ],
)
def test_a_citation_that_does_not_exist_is_caught(citation: Citation, at: Lookup) -> None:
    result = checked(citation, at=at)
    assert result.unresolved == (citation,)
    assert result.verified == ()


class CorruptCorpus:
    """A `CitationSource` whose rows don't fit `Provision`, as a corrupt database row would."""

    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: object,
        *,
        include_held_out: bool = False,
    ) -> Provision:
        return Provision.model_validate({"provision_id": provision_id})

    def omnibus(self, provision_id: str, language: Language, as_of: object) -> Provision:
        return Provision.model_validate({"provision_id": provision_id})


def test_a_corrupt_corpus_row_is_raised_not_read_as_a_missing_citation() -> None:
    with pytest.raises(ValidationError):
        resolve(ART_5_1_BA, lookup(), CorruptCorpus())


def test_guidance_resolves_without_a_law_version_and_keeps_english_only() -> None:
    guidance = cite("guide:guide-art50:para:1", "guide-art50", None).model_copy(
        update={"english_only": True}
    )
    (verified,) = checked(guidance, at=lookup(language=Language.DE)).verified
    assert (verified.law_version, verified.language, verified.english_only) == (
        None,
        Language.EN,
        True,
    )
    assert not verified.changed_by_omnibus


def test_a_retrievable_example_resolves() -> None:
    example = cite("guide:guide-high-risk-annex-iii:ex:015", "guide-high-risk-annex-iii", None)
    assert checked(example).verified[0].provision_id == example.provision_id


def test_a_citation_of_the_omnibus_itself_resolves_through_its_own_lookup() -> None:
    omnibus = cite("art:1:1", "omnibus", law_version=None)
    (verified,) = checked(omnibus).verified
    assert verified.document_id == "omnibus"
    assert "point (g) is replaced" in verified.quote
    assert not verified.changed_by_omnibus


def test_the_built_omnibus_never_returns_a_held_out_row() -> None:
    """The in-memory twin of `test_the_omnibus_lookup_never_returns_a_held_out_row` (db)."""
    omnibus = DocumentRow(
        doc_key=OMNIBUS_DOC, title="Test Omnibus", celex=None, doc_type="law", is_amending=True,
        status="final", law_version=None, language="en", published_on=date(2026, 7, 24),
        in_force_from=date(2026, 7, 27), source_url="https://eur-lex.europa.eu/", sha256="c" * 64,
    )  # fmt: skip
    planted = ProvisionRow(
        "art:1:2", None, None, None, "A held-out example.", date(2026, 7, 27),
        source_example_id="hr-ex-001", is_held_out=True,
    )  # fmt: skip
    with pytest.raises(ProvisionNotFoundError):
        BuiltCorpus((DocumentLoad(omnibus, (planted,)),)).omnibus("art:1:2", Language.EN, None)


def test_a_recital_resolves_from_the_original_text() -> None:
    recital = cite("recital:27", ORIGINAL, LawVersion.ORIGINAL)
    assert checked(recital).verified[0].law_version is LawVersion.ORIGINAL


# --- The validator around a check node ------------------------------------------------------------


def decided(*citations: Citation, name: StepName = StepName.PROHIBITED) -> CheckOutcome:
    step = StepResult(step=name, decision="Art. 5(1)(ba) applies.", citations=citations)
    return CheckOutcome(step=step, matched=name is StepName.PROHIBITED)


class ScriptedNode:
    """A check node returning `outcomes` in turn (the last one again), counting its calls."""

    def __init__(self, *outcomes: CheckOutcome) -> None:
        self._outcomes = outcomes
        self.calls = 0

    def __call__(self, _state: EngineState) -> CheckOutcome:
        self.calls += 1
        return self._outcomes[min(self.calls, len(self._outcomes)) - 1]


def test_a_step_whose_citations_resolve_runs_once_and_is_marked() -> None:
    node = ScriptedNode(decided(ART_5_1_BA, cite("art:5:1:a")))
    outcome = built_validator().checked(node)(STATE)
    assert node.calls == 1
    assert outcome.step.status is Status.DECIDED
    assert [c.changed_by_omnibus for c in outcome.step.citations] == [True, False]
    assert outcome.matched


def test_an_injected_fake_citation_is_retried_once_then_flagged() -> None:
    node = ScriptedNode(decided(ART_5_1_BA, FAKE))
    outcome = built_validator().checked(node)(STATE)
    assert node.calls == 2
    step = outcome.step
    assert (step.status, step.error) == (Status.NEEDS_MORE_INFORMATION, CITATION_UNVERIFIED)
    assert [c.provision_id for c in step.citations] == ["art:5:1:ba"]
    assert step.decision.endswith(UNVERIFIED[Language.EN])
    assert outcome.matched  # the finding stays: the step is only unverified


def test_the_retry_that_cites_only_real_provisions_is_kept() -> None:
    node = ScriptedNode(decided(FAKE), decided(ART_5_1_BA))
    outcome = built_validator().checked(node)(STATE)
    assert node.calls == 2
    assert (outcome.step.status, outcome.step.error) == (Status.DECIDED, None)
    assert [c.provision_id for c in outcome.step.citations] == ["art:5:1:ba"]


MISSING = FollowUpQuestion(id="eu_use", text="Is the system used in the EU?")
OPEN = OpenQuestion(question="Is it manipulation?", readings=("Yes", "No"))


@pytest.mark.parametrize(
    ("status", "extra"),
    [
        (Status.LEGALLY_AMBIGUOUS, {"open_question": OPEN}),
        (Status.NEEDS_MORE_INFORMATION, {"missing_fact": MISSING}),
    ],
)
def test_an_uncertain_step_keeps_its_status_and_question(
    status: Status, extra: dict[str, object]
) -> None:
    step = StepResult.model_validate(
        {
            "step": StepName.SCOPE,
            "decision": "Uncertain.",
            "citations": (FAKE,),
            "status": status,
            **extra,
        }
    )
    node = ScriptedNode(CheckOutcome(step=step))
    flagged = built_validator().checked(node)(STATE).step
    assert (flagged.status, flagged.error) == (status, CITATION_UNVERIFIED)
    assert (flagged.open_question, flagged.missing_fact) == (step.open_question, step.missing_fact)


def test_a_refused_step_keeps_its_refusal_error_without_a_retry() -> None:
    """Running a refused step again would only be refused again (decision 029)."""
    step = StepResult(
        step=StepName.PROHIBITED,
        decision="Blocked.",
        citations=(FAKE,),
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=MISSING,
        error=PROVIDER_REFUSAL,
    )
    node = ScriptedNode(CheckOutcome(step=step, matched=True))
    flagged = built_validator().checked(node)(STATE).step
    assert node.calls == 1
    assert (flagged.error, flagged.citations) == (PROVIDER_REFUSAL, ())


def test_the_flag_is_in_the_run_language() -> None:
    node = ScriptedNode(decided(FAKE))
    german: EngineState = {**STATE, "language": Language.DE}
    flagged = built_validator().checked(node)(german).step
    assert flagged.decision.endswith(UNVERIFIED[Language.DE])


def test_a_flagged_stopping_step_still_ends_the_run() -> None:
    """A decided Art. 5 match with a fake citation is unverified, not uncertain: the run ends
    prohibited, as `can_end_run` allows (E1), and the result keeps its contract."""
    nodes = scripted_nodes(Script(checks={StepName.PROHIBITED: decided(ART_5_1_BA, FAKE)}))
    checks = built_validator().checks(nodes.checks)
    graph = build_graph(type(nodes)(facts=nodes.facts, checks=checks, finalize=nodes.finalize))
    result = graph.invoke(ENGINE_INPUT)["result"]
    assert isinstance(result, ClassificationResult)
    assert result.risk_class is RiskClass.PROHIBITED
    assert [s.step for s in result.steps] == [StepName.SCOPE, StepName.PROHIBITED]
    assert result.steps[-1].error == CITATION_UNVERIFIED
    assert result.status is Status.NEEDS_MORE_INFORMATION


def test_a_step_without_citations_needs_no_corpus() -> None:
    validator = CitationValidator(source=None, omnibus=omnibus_changes())
    step = StepResult(step=StepName.SCOPE, decision="In scope.")
    assert validator.check(step, STATE) == CitationCheck(verified=(), unresolved=())
