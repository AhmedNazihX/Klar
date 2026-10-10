"""The staged engine as the benchmark runner's `engine` classifier (E10, over V1's `Classifier`).

Each case runs `run_classification` on the case's own date (`ClassifierInput.as_of`, B5c), or the
run's date when it has none, on the amended text, with the case's exclusions and, in the gap
run only, the held-out examples (`ClassifierInput.include_held_out`). It reports the
run's cost, tokens, LangSmith trace id and each node's calls by the model that served them (a
request the engine provider refused and the second model answered shows under both, decision
033). A run that fails after spending raises `ClassifierFailedError(cost_usd, tokens, cause)`,
with the same models, so the runner's cost cap and totals count it.
A reply without its cost is logged, since the stored cost then undercounts.
"""

import logging
from datetime import date

from aiact.engine import ClassificationFailedError, ClassifyRequest, run_classification
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.eval.runner import (
    Classification,
    ClassifierFailedError,
    ClassifierInfo,
    ClassifierInput,
)
from aiact.llm.routing import require_setting
from aiact.schemas import LawVersion
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class EngineClassifier:
    """`classify_system`'s pipeline for `aiact evaluate run --classifier engine`. Thread-safe:
    every case builds its own nodes and meter."""

    def __init__(
        self, settings: Settings | None = None, build_nodes: NodeBuilder = engine_nodes
    ) -> None:
        """`build_nodes` replaces the engine's nodes (tests). Raises `LLMConfigError` when
        `ENGINE_MODEL`, `ENGINE_PROVIDER`, `EMBEDDING_MODEL` or `EMBEDDING_PROVIDER` is not set."""
        self._settings = settings or get_settings()
        self._build_nodes = build_nodes
        s = self._settings
        self.info = ClassifierInfo(
            model=require_setting(s.engine_model, "ENGINE_MODEL"),
            provider=require_setting(s.engine_provider, "ENGINE_PROVIDER"),
            embedding={
                "model": require_setting(s.embedding_model, "EMBEDDING_MODEL"),
                "provider": require_setting(s.embedding_provider, "EMBEDDING_PROVIDER"),
                "dimensions": s.embedding_dimensions,
            },
            retrieval={"search": "hybrid_rrf", "max_distance": None},
        )

    def classify(self, request: ClassifierInput) -> Classification:
        engine_request = ClassifyRequest(
            description=request.description,
            language=request.language,
            law_version=LawVersion.AMENDED,
            as_of=request.as_of or date.today(),
        )
        try:
            run = run_classification(
                engine_request,
                settings=self._settings,
                build_nodes=self._build_nodes,
                exclude_source_example_ids=request.exclude_source_example_ids,
                include_held_out=request.include_held_out,
            )
        except ClassificationFailedError as exc:
            usage = exc.usage
            if usage.cost_usd > 0 or usage.tokens > 0:
                raise ClassifierFailedError(
                    usage.cost_usd, usage.tokens, exc, models=usage.models_by_node()
                ) from exc
            raise
        usage = run.usage
        if not usage.is_cost_complete:
            logger.warning(
                "a reply of trace %s came without its cost; the stored $%.6f undercounts",
                run.trace_id or "-",
                usage.cost_usd,
            )
        return Classification(
            result=run.result,
            cost_usd=usage.cost_usd,
            tokens=usage.tokens,
            trace_id=run.trace_id,
            models=usage.models_by_node(),
        )
