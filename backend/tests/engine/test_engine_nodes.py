"""The engine's own nodes as `engine_nodes` builds them for a run (E10), run one by one offline:
the model is a fake that answers with a paid reply cut off mid-answer, and the corpus functions
(`get_provision`, `search_ai_act`) and connections are replaced by recorders. Shows that every
node's model calls and query embeddings are counted under its own name, that every retrieval
call of a real check carries the run's `include_held_out` (before the reply, and after it on a
parseable reply and on a refusal, the citation validator's lookups included), and that a node's
broken-output error doesn't carry the reply's text. The citation validator's re-run is counted
too."""

import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine import citations
from aiact.engine import classify as classify_module
from aiact.engine.citations import CitationValidator, OmnibusChanges
from aiact.engine.classify import engine_nodes
from aiact.engine.clients import NODE_TOKENS
from aiact.engine.graph import CheckNode, EngineNodes
from aiact.engine.nodes import corpus as corpus_module
from aiact.engine.nodes import high_risk, prohibited, scope, transparency
from aiact.engine.nodes.high_risk_texts import REFUSAL_CITATIONS
from aiact.engine.nodes.prohibited_practices import APPLICATION_DATES
from aiact.engine.nodes.transparency_duties import MarketTiming
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
from tests.engine.nodes import test_high_risk, test_prohibited, test_scope, test_transparency

AS_OF = date(2026, 10, 6)
SECRET = "the night shifts of our Leipzig depot"
SHORT_SECRET = "Leipzig"
"""Short enough that pydantic would quote it whole in an `input_value`."""
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
    """Stands in for `get_provision` and `search_ai_act` in the checks' corpus reader and the
    citation validator, noting each call's module and opt-in; a search embeds its query as the
    real one does."""

    calls: list[tuple[str, str, bool]] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    """Each call's provision id, or `search`, in the order of `calls`."""
    replied_at: int | None = None
    """How many calls came before the model replied (set by `ReplyMarker`)."""

    def after_reply(self) -> list[tuple[str, str, str, bool]]:
        """The calls made after the model replied: (module, function, target, opt-in)."""
        start = self.replied_at if self.replied_at is not None else len(self.calls)
        rows = zip(self.calls[start:], self.targets[start:], strict=True)
        return [(module, function, target, flag) for (module, function, flag), target in rows]

    def recorders(
        self, module: str
    ) -> tuple[Callable[..., Provision], Callable[..., SearchResults]]:
        def get_provision(provision_id: str, *args: object, **kwargs: object) -> Provision:
            self.calls.append((module, "get_provision", kwargs["include_held_out"] is True))
            self.targets.append(provision_id)
            return fake_provision(provision_id)

        def search_ai_act(
            query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
        ) -> SearchResults:
            self.calls.append((module, "search_ai_act", kwargs["include_held_out"] is True))
            self.targets.append("search")
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
    for module in (corpus_module, citations):
        get, search = corpus.recorders(module.__name__.rsplit(".", 1)[-1])
        monkeypatch.setattr(module, "get_provision", get)
        if module is not citations:
            monkeypatch.setattr(module, "search_ai_act", search)
        monkeypatch.setattr(module, "connect", no_connection)

    def fake_engine_chats(settings: Settings) -> dict[str, GenericFakeChatModel]:
        return {
            node: GenericFakeChatModel(messages=iter([paid_reply(), paid_reply()]))
            for node in NODE_TOKENS
        }

    monkeypatch.setattr(classify_module, "engine_chats", fake_engine_chats)
    monkeypatch.setattr(classify_module, "engine_embeddings", CostedEmbeddings)
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
    assert modules == {"corpus"}  # every check reads through the one corpus reader
    assert {function for _, function, _ in offline.calls} == {"get_provision", "search_ai_act"}
    assert all(flag is include_held_out for _, _, flag in offline.calls)


def test_a_broken_output_error_carries_no_reply_text(offline: Corpus) -> None:
    errors = run_each_node(engine_nodes(settings(), UsageMeter()), include_held_out=False)
    for name, error in errors.items():
        assert error.__cause__ is None, name
        assert error.__suppress_context__, name
        written = "".join(traceback.format_exception(error))
        assert "input_value" not in written, name
        assert SHORT_SECRET not in written, name


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


# --- After the reply: a parseable answer and a refusal ------------------------------------------


class ReplyMarker(BaseCallbackHandler):
    """Notes in the corpus recorder when the model is asked, so the calls after it are known."""

    def __init__(self, corpus: Corpus) -> None:
        self._corpus = corpus

    def on_chat_model_start(self, *args: object, **kwargs: object) -> None:
        self._corpus.replied_at = len(self._corpus.calls)


REFUSAL = AIMessage(
    content="I'm sorry, but I cannot assist with that request.",
    response_metadata={"finish_reason": "content_filter"},
)
PARSEABLE: dict[StepName, Callable[[], str]] = {
    StepName.SCOPE: lambda: test_scope.scope_answer().model_dump_json(),
    StepName.PROHIBITED: lambda: test_prohibited.answer(
        test_prohibited.WORKPLACE_EMOTIONS
    ).model_dump_json(),
    StepName.HIGH_RISK: lambda: test_high_risk.answer(
        test_high_risk.RANKS_APPLICANTS
    ).model_dump_json(),
    StepName.TRANSPARENCY: lambda: (
        test_transparency.answer(MarketTiming.PLACED_BEFORE, **test_transparency.MARKS)
    ).model_dump_json(),
}
"""A reply each retrieving check reads and cites from: a system in scope, workplace emotion
recognition, applicant ranking (Annex III 4(a)), and synthetic content placed on the market
before 2 August 2026 (the Art. 111(4) grace period)."""
NODE_LOOKUPS: dict[tuple[StepName, str], tuple[str, str]] = {
    (StepName.SCOPE, "answer"): ("corpus", "art:3:1"),
    (StepName.PROHIBITED, "answer"): ("corpus", "art:5:1:f"),
    (StepName.PROHIBITED, "refusal"): ("corpus", APPLICATION_DATES),
    (StepName.HIGH_RISK, "answer"): ("corpus", "art:6:3"),
    (StepName.HIGH_RISK, "refusal"): ("corpus", REFUSAL_CITATIONS[0]),
    (StepName.TRANSPARENCY, "answer"): ("corpus", "art:111:4"),
}
"""A lookup each check makes only after the reply (Art. 113(a) and Art. 6(1) on a refusal)."""


def real_check(name: StepName, reply: AIMessage, corpus: Corpus) -> CheckNode:
    """The check with no library (it reads through the recorded corpus functions), wrapped by
    the citation validator as `engine_nodes` wraps it."""
    run_settings = settings()
    chat = GenericFakeChatModel(messages=iter([reply, reply]), callbacks=[ReplyMarker(corpus)])
    embedder = UsageMeter().embedder(name, CostedEmbeddings(run_settings))
    classes = {
        StepName.SCOPE: scope.ScopeCheck,
        StepName.PROHIBITED: prohibited.ProhibitedCheck,
        StepName.HIGH_RISK: high_risk.HighRiskCheck,
        StepName.TRANSPARENCY: transparency.TransparencyCheck,
    }
    check = classes[name](run_settings, chat=chat, embedder=embedder)
    return CitationValidator(settings=run_settings).checked(check)


@pytest.mark.parametrize("include_held_out", [True, False])
@pytest.mark.parametrize("kind", ["answer", "refusal"])
@pytest.mark.parametrize("name", RETRIEVING, ids=lambda name: name.value)
def test_every_corpus_call_after_the_reply_passes_the_runs_opt_in(
    offline: Corpus, name: StepName, kind: str, include_held_out: bool
) -> None:
    reply = AIMessage(content=PARSEABLE[name]()) if kind == "answer" else REFUSAL
    outcome = real_check(name, reply, offline)(state(include_held_out=include_held_out))
    assert outcome.step.step is name
    after = offline.after_reply()
    assert after, "no corpus call after the reply"
    assert all(flag is include_held_out for _, _, _, flag in after), after
    assert all(flag is include_held_out for _, _, flag in offline.calls)
    assert any(module == "citations" for module, _, _, _ in after)  # the validator's lookups
    expected = NODE_LOOKUPS.get((name, kind))
    if expected is not None:
        assert expected in {(module, target) for module, _, target, _ in after}, after
