"""The engine's own nodes as `engine_nodes` builds them for a run (E10), run one by one offline:
the model is a fake that answers with a paid reply cut off mid-answer, and the corpus functions
(`get_provision`, `search_ai_act`) and connections are replaced by recorders. Shows that every
node's model calls and query embeddings are counted under its own name, that every retrieval
call of a real check carries the run's `include_held_out`, and that a node's broken-output error
doesn't carry the reply's text. The citation validator's re-run is counted too."""

import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine import classify as classify_module
from aiact.engine.citations import CitationValidator, OmnibusChanges
from aiact.engine.classify import engine_nodes
from aiact.engine.graph import EngineNodes
from aiact.engine.nodes import (
    guideline_retrieval,
    high_risk,
    high_risk_retrieval,
    prohibited,
    scope,
    transparency,
)
from aiact.engine.state import CheckOutcome, EngineState
from aiact.engine.usage import MeteredEmbedder, UsageMeter
from aiact.llm.embeddings import EmbeddingBatch, OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchResults
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    Citation,
    DocumentStatus,
    Language,
    LawVersion,
    StepName,
    StepResult,
)
from aiact.settings import Settings

AS_OF = date(2026, 10, 6)
SECRET = "the night shifts of our Leipzig depot"
CHAT_COST = 0.001
EMBED_COST = 0.00001
RETRIEVING = (StepName.SCOPE, StepName.PROHIBITED, StepName.HIGH_RISK, StepName.TRANSPARENCY)
"""The checks that read the corpus; facts and role_obligations don't."""


def settings() -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr("k"),
        engine_model="openai/gpt-6-luna-20260922",
        engine_provider="azure/eu",
        embedding_model="qwen/qwen3-embedding-8b",
        embedding_provider="nebius",
    )


def state(*, include_held_out: bool) -> EngineState:
    return {
        "description": f"We use a tool that ranks applicants for {SECRET}.",
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "exclude_source_example_ids": ("hr-ex-001",),
        "include_held_out": include_held_out,
    }


def paid_reply() -> AIMessage:
    """A reply cut off mid-answer, quoting the description, billed at `CHAT_COST`."""
    return AIMessage(
        content='{"facts": [{"text": "The tool ranks applicants for ' + SECRET,
        response_metadata={"cost": CHAT_COST},
        usage_metadata={"input_tokens": 900, "output_tokens": 100, "total_tokens": 1000},
    )


def fake_provision(provision_id: str) -> Provision:
    return Provision(
        provision_id=provision_id,
        doc_key="ai-act-consolidated",
        document_title="AI Act",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.CONSOLIDATED,
        language=Language.EN,
        english_only=False,
        heading=None,
        text=f"The text of {provision_id}.",
        valid_from=date(2024, 8, 1),
        valid_to=None,
        disclaimer=DISCLAIMER[Language.EN],
    )


class CostedEmbeddings(OpenRouterEmbeddings):
    """Embeds without a network call, billing `EMBED_COST` per request."""

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings=settings)

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(vectors=[[1.0, 0.0]] * len(texts), tokens=5, cost_usd=EMBED_COST)


@dataclass
class Corpus:
    """Stands in for `get_provision` and `search_ai_act` in every node's retrieval module,
    noting each call's module and opt-in; a search embeds its query as the real one does."""

    calls: list[tuple[str, str, bool]] = field(default_factory=list)

    def recorders(
        self, module: str
    ) -> tuple[Callable[..., Provision], Callable[..., SearchResults]]:
        def get_provision(provision_id: str, *args: object, **kwargs: object) -> Provision:
            self.calls.append((module, "get_provision", kwargs["include_held_out"] is True))
            return fake_provision(provision_id)

        def search_ai_act(
            query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
        ) -> SearchResults:
            self.calls.append((module, "search_ai_act", kwargs["include_held_out"] is True))
            embedder = kwargs.get("embedder")
            if embedder is not None:
                assert isinstance(embedder, MeteredEmbedder)  # the run's, counted
                embedder.embed_query(query)
            return SearchResults(
                query=query,
                language=language,
                law_version=law_version,
                as_of=as_of,
                hits=(),
                max_distance=None,
                found=False,
                disclaimer=DISCLAIMER[language],
            )

        return get_provision, search_ai_act


@contextmanager
def no_connection() -> Iterator[None]:
    yield None


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> Corpus:
    """Fake model, costed embeddings, recorded corpus and no database for `engine_nodes`."""
    corpus = Corpus()
    for module in (scope, guideline_retrieval, high_risk_retrieval):
        get, search = corpus.recorders(module.__name__.rsplit(".", 1)[-1])
        monkeypatch.setattr(module, "get_provision", get)
        monkeypatch.setattr(module, "search_ai_act", search)
    for module in (prohibited, high_risk, transparency):
        monkeypatch.setattr(module, "connect", no_connection)

    def fake_engine_model(*, max_tokens: int, settings: Settings) -> GenericFakeChatModel:
        return GenericFakeChatModel(messages=iter([paid_reply(), paid_reply()]))

    monkeypatch.setattr(classify_module, "engine_chat_model", fake_engine_model)
    monkeypatch.setattr(classify_module, "OpenRouterEmbeddings", CostedEmbeddings)
    return corpus


def run_each_node(nodes: EngineNodes, *, include_held_out: bool) -> dict[str, BaseException]:
    """Every node run once on the cut-off reply; each fails on it. Returns the errors by node."""
    errors: dict[str, BaseException] = {}
    run_state = state(include_held_out=include_held_out)
    runners = {"facts": nodes.facts, **{name.value: nodes.checks[name] for name in STEP_ORDER}}
    for name, node in runners.items():
        with pytest.raises(ValueError) as raised:
            node(run_state)
        errors[name] = raised.value
    return errors


def test_every_node_is_metered_under_its_own_name_with_its_embeddings(offline: Corpus) -> None:
    meter = UsageMeter()
    run_each_node(engine_nodes(settings(), meter), include_held_out=False)
    by_node = meter.usage().by_node
    assert set(by_node) == {"facts", *(name.value for name in STEP_ORDER)}
    for name, usage in by_node.items():
        searches = usage.calls - 1  # one model call; the rest are query embeddings
        is_retrieving = name in {step.value for step in RETRIEVING}
        assert (searches > 0) is is_retrieving, name
        assert usage.cost_usd == pytest.approx(CHAT_COST + searches * EMBED_COST), name


@pytest.mark.parametrize("include_held_out", [True, False])
def test_every_real_check_passes_the_runs_opt_in_to_every_retrieval_call(
    offline: Corpus, include_held_out: bool
) -> None:
    run_each_node(engine_nodes(settings(), UsageMeter()), include_held_out=include_held_out)
    modules = {module for module, _, _ in offline.calls}
    assert modules == {"scope", "guideline_retrieval", "high_risk_retrieval"}
    assert {function for _, function, _ in offline.calls} == {"get_provision", "search_ai_act"}
    assert all(flag is include_held_out for _, _, flag in offline.calls)


def test_a_broken_output_error_carries_no_reply_text(offline: Corpus) -> None:
    errors = run_each_node(engine_nodes(settings(), UsageMeter()), include_held_out=False)
    for name, error in errors.items():
        assert error.__cause__ is None, name
        assert error.__suppress_context__, name
        assert SECRET not in "".join(traceback.format_exception(error)), name


# --- The citation validator's re-run ------------------------------------------------------------


class NothingResolves:
    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: date | None,
        *,
        include_held_out: bool = False,
    ) -> Provision:
        raise ProvisionNotFoundError(provision_id)

    def omnibus(self, provision_id: str, language: Language, as_of: date | None) -> Provision:
        raise ProvisionNotFoundError(provision_id)


def test_the_validators_rerun_counts_both_paid_replies() -> None:
    meter = UsageMeter()
    replies = [
        AIMessage(content="{}", response_metadata={"cost": cost}, usage_metadata=usage)
        for cost, usage in (
            (0.002, {"input_tokens": 90, "output_tokens": 10, "total_tokens": 100}),
            (0.003, {"input_tokens": 180, "output_tokens": 20, "total_tokens": 200}),
        )
    ]
    model = GenericFakeChatModel(
        messages=iter(replies), callbacks=[meter.chat_callback(StepName.HIGH_RISK)]
    )
    cited = Citation(
        provision_id="annex:III:99",
        document_id="ai-act-consolidated",
        law_version=LawVersion.AMENDED,
        language=Language.EN,
        quote="Not in the Act.",
    )

    def check(_state: EngineState) -> CheckOutcome:
        model.invoke("classify")
        step = StepResult(step=StepName.HIGH_RISK, decision="Cites a point.", citations=(cited,))
        return CheckOutcome(step=step)

    validator = CitationValidator(
        source=NothingResolves(), omnibus=OmnibusChanges(in_force_from=AS_OF, targets=frozenset())
    )
    outcome = validator.checked(check)(state(include_held_out=False))
    assert outcome.step.error == "citation_unverified"
    usage = meter.usage().by_node["high_risk"]
    assert usage.calls == 2
    assert usage.cost_usd == pytest.approx(0.005)
    assert usage.tokens == 300
